# accounts/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
import random
from .permissions import IsCustomerOrAdmin,IsProviderOrAdmin # Add this import at the top if not already imported
from utils.cloudinary import upload_image, upload_video
from .models import Admin, Customer, Provider, OTPVerification, BiometricToken, CustomerAddress,ProviderAddress,City,Region
from .serializers import (
    AdminLoginSerializer, AdminSerializer,
    CustomerRegisterSerializer, CustomerSerializer,
    ProviderRegisterSerializer, ProviderSerializer,CustomerAdminSerializer,CitySerializer,
    SendOTPSerializer, VerifyOTPSerializer,CustomerUpdateSerializer, CityWriteSerializer, ProviderAddressSerializer,RegionWriteSerializer, ProviderUpdateSerializer,RegisterBiometricSerializer, BiometricLoginSerializer, CustomerAddressSerializer
)
from rest_framework_simplejwt.exceptions import TokenError
from .permissions import IsCustomer, IsProvider
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings


# ==================== Helper ====================

def get_tokens_for_user(user, user_type):
    """بيعمل JWT tokens من غير ما يتقيد بـ AUTH_USER_MODEL"""
    token = RefreshToken()
    
    # بيانات اليوزر في الـ payload يدوياً
    token[api_settings.USER_ID_CLAIM] = str(user.id)
    token['user_type'] = user_type
    
    return {
        'refresh': str(token),
        'access': str(token.access_token),
    }

def generate_otp():
    return str(random.randint(100000, 999999))

import requests
from django.conf import settings

def format_phone(phone_number):
    """بيحول الرقم لـ 966xxxxxxxxx"""
    phone = phone_number.strip().replace(' ', '')
    if phone.startswith('+966'):
        phone = phone[1:]          # شيل الـ +  → 966xxxxxxxxx
    elif phone.startswith('966'):
        pass                       # already correct
    elif phone.startswith('05') or phone.startswith('5'):
        phone = phone.lstrip('0')  # شيل الصفر → 5xxxxxxxxx
        phone = '966' + phone      # → 9665xxxxxxxxx
    return phone


def send_sms(phone_number, code):
    url = "https://www.msegat.com/gw/sendsms.php"

    payload = {
        "userName": settings.MSEGAT_USERNAME,
        "apiKey": settings.MSEGAT_API_KEY,
        "userSender": settings.MSEGAT_SENDER,
        "numbers": format_phone(phone_number),
        "msg": f"رمز التحقق: {code}",
        "msgEncoding": "UTF8",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        if data.get("code") == "1" or data.get("message") == "Success":
            print(f"[Msegat] OTP sent to {phone_number}")
            return True
        else:
            print(f"[Msegat] Failed: {data}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"[Msegat] Error: {e}")
        return False

# ==================== ADMIN VIEWS ====================

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        admin = authenticate(request, username=email, password=password)

        if not admin:
            return Response(
                {'error': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not admin.is_active:
            return Response(
                {'error': 'Account is inactive.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # آبديت الـ last_login
        admin.last_login = timezone.now()
        admin.save(update_fields=['last_login'])

        tokens = get_tokens_for_user(admin, 'admin')

        return Response({
            'tokens': tokens,
            'user': AdminSerializer(admin).data
        }, status=status.HTTP_200_OK)


# ==================== OTP VIEWS ====================
class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        user_type = serializer.validated_data['user_type']

        OTPVerification.objects.filter(
            phone_number=phone_number,
            user_type=user_type,
            is_used=False
        ).delete()

        code = generate_otp()

        OTPVerification.objects.create(
            phone_number=phone_number,
            user_type=user_type,
            code=code
        )

        # send_sms(phone_number, code)  # commented out during development

        response_data = {'message': 'OTP sent successfully.'}

        # ✅ DEV ONLY: return OTP in response
        if settings.DEBUG:
            response_data['otp'] = code

        return Response(response_data, status=status.HTTP_200_OK)
    
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        user_type = serializer.validated_data['user_type']
        otp = serializer.validated_data['otp']
        device_token = request.data.get('device_token')
        # ماركت الـ OTP كـ used
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        # دور على اليوزر
        if user_type == 'customer':
            user, created = Customer.objects.get_or_create(
                phone_number=phone_number,
                defaults={'name': '', 'is_phone_verified': True}
            )
            if not created and not user.is_phone_verified:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified'])

            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            tokens = get_tokens_for_user(user, 'customer')
            user_data = CustomerSerializer(user).data

        else:  # provider
            try:
                user = Provider.objects.get(phone_number=phone_number)
            except Provider.DoesNotExist:
                return Response(
                    {'error': 'Provider account not found. Please register first.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if not user.is_phone_verified:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified'])

            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            tokens = get_tokens_for_user(user, 'provider')
            user_data = ProviderSerializer(user).data

        if device_token:
            user.device_token = device_token
            user.save(update_fields=['device_token'])
        return Response({
            'tokens': tokens,
            'user': user_data
        }, status=status.HTTP_200_OK)


# ==================== REGISTER VIEWS ====================

class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()

        return Response(
            {'message': 'Registration successful. Please verify your phone number.'},
            status=status.HTTP_201_CREATED
        )

class ProviderRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # ارفع الـ contract_image لو موجود
        contract_image_url = None
        if 'contract_image' in request.FILES:
            contract_image_url = upload_image(
                request.FILES['contract_image'],
                folder="contracts"
            )

        data = request.data.copy()
        if contract_image_url:
            data['contract_image'] = contract_image_url

        serializer = ProviderRegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.save()

        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type == 'admin':
            provider.is_phone_verified = True
            provider.save(update_fields=['is_phone_verified'])

        return Response(
            {'message': 'Registration submitted. Pending admin approval.'},
            status=status.HTTP_201_CREATED
        )
    
# ==================== LOGOUT ====================

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'error': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {'message': 'Logged out successfully.'},
            status=status.HTTP_200_OK
        )


# ==================== CUSTOMER PROFILE ====================

class CustomerProfileView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        serializer = CustomerSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = CustomerUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            CustomerSerializer(request.user).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request):
        user = request.user
        # Blacklist الـ token قبل الحذف
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass  # نكمل الحذف حتى لو الـ token مش valid

        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(
            {'message': 'Account deactivated successfully.'},
            status=status.HTTP_200_OK
        )


# ==================== PROVIDER PROFILE ====================

class ProviderProfileView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        serializer = ProviderSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = ProviderUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            ProviderSerializer(request.user).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request):
        user = request.user
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass

        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(
            {'message': 'Account deactivated successfully.'},
            status=status.HTTP_200_OK
        )
    
# ==================== ADMIN - PROVIDER MANAGEMENT ====================

class ProviderBlockView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not provider.is_active and not provider.is_approved:
            return Response(
                {'error': 'Provider is already blocked.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        provider.is_active = False
        provider.is_approved = False
        provider.save(update_fields=['is_active', 'is_approved'])

        return Response(
            {
                'message': f'Provider {provider.name} has been blocked.',
                'provider_id': str(provider.id),
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, provider_id):
        """إلغاء الـ block"""
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if provider.is_active and provider.is_approved:
            return Response(
                {'error': 'Provider is not blocked.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        provider.is_active = True
        provider.is_approved = True
        provider.save(update_fields=['is_active', 'is_approved'])

        return Response(
            {
                'message': f'Provider {provider.name} has been unblocked.',
                'provider_id': str(provider.id),
            },
            status=status.HTTP_200_OK
        )
from .serializers import ProviderAdminSerializer

class ProviderListView(APIView):
    """قائمة كل الـ providers مع فلترة"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get('status')  # active, blocked, pending

        providers = Provider.objects.all().order_by('-created_at')

        if status_filter == 'active':
            providers = providers.filter(is_active=True, is_approved=True)
        elif status_filter == 'blocked':
            providers = providers.filter(is_active=False, is_approved=False)
        elif status_filter == 'pending':
            providers = providers.filter( is_approved=False, is_active=True)

        serializer = ProviderAdminSerializer(providers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProviderDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProviderAdminSerializer(provider)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProviderUpdateSerializer(
            provider,
            data=request.data,
            partial=True,
            context={'request': request}   # ← ضيف السطر ده
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProviderAdminSerializer(provider).data, status=status.HTTP_200_OK)

    def delete(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=status.HTTP_404_NOT_FOUND)
        provider.delete()
        return Response({'message': 'Provider deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

class ProviderApproveView(APIView):
    """موافقة على provider جديد"""
    permission_classes = [IsAdminUser]

    def post(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if provider.is_approved:
            return Response(
                {'error': 'Provider is already approved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not provider.is_phone_verified:
            return Response(
                {'error': 'Provider phone is not verified yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        provider.is_approved = True
        provider.save(update_fields=['is_approved'])

        return Response(
            {
                'message': f'Provider {provider.name} has been approved.',
                'provider_id': str(provider.id),
            },
            status=status.HTTP_200_OK
        )
    


class RegisterBiometricView(APIView):
    """
    بعد OTP login ناجح، الموبايل يبعت device_id
    وبيرجع له biometric_token يحفظه في Keychain/Keystore
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RegisterBiometricSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_id = serializer.validated_data['device_id']

        # تحديد user_type من الـ JWT payload
        user_type = request.auth.payload.get('user_type')
        if user_type not in ('customer', 'provider'):
            return Response(
                {'error': 'Biometric login not supported for this account type.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_token = BiometricToken.generate_token()

        # لو الجهاز ده سبق وسجّل، حدّث الـ token
        BiometricToken.objects.update_or_create(
            user_id=str(request.user.id),
            user_type=user_type,
            device_id=device_id,
            defaults={
                'token': new_token,
                'is_active': True,
            }
        )

        return Response(
            {'biometric_token': new_token},
            status=status.HTTP_201_CREATED
        )


class BiometricLoginView(APIView):
    """
    الموبايل بيبعت biometric_token + device_id
    بعد ما البصمة تنجح محلياً على الجهاز
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BiometricLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        biometric = serializer.validated_data['biometric']
        user_type = biometric.user_type
        user_id = biometric.user_id

        # جيب اليوزر حسب النوع
        try:
            if user_type == 'customer':
                user = Customer.objects.get(id=user_id, is_active=True)
            else:
                user = Provider.objects.get(id=user_id, is_active=True, is_approved=True)
        except (Customer.DoesNotExist, Provider.DoesNotExist):
            return Response(
                {'error': 'Account not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )
        device_token = request.data.get('device_token')
        # آبديت last_used
        biometric.last_used = timezone.now()
        biometric.save(update_fields=['last_used'])

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        tokens = get_tokens_for_user(user, user_type)

        if user_type == 'customer':
            user_data = CustomerSerializer(user).data
        else:
            user_data = ProviderSerializer(user).data

        if device_token:
            user.device_token = device_token
            user.save(update_fields=['device_token'])

        return Response({
            'tokens': tokens,
            'user': user_data
        }, status=status.HTTP_200_OK)


class RevokeBiometricView(APIView):

    """إلغاء البصمة من الجهاز (مثلاً من إعدادات الحساب)"""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = RegisterBiometricSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_id = serializer.validated_data['device_id']
        user_type = request.auth.payload.get('user_type')

        BiometricToken.objects.filter(
            user_id=str(request.user.id),
            user_type=user_type,
            device_id=device_id
        ).update(is_active=False)

        return Response(
            {'message': 'Biometric login revoked for this device.'},
            status=status.HTTP_200_OK
        )
    

class CustomerAddressView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        """كل عناوين العميل"""
        addresses = CustomerAddress.objects.filter(customer=request.user)
        return Response(
            CustomerAddressSerializer(addresses, many=True).data
        )

    def post(self, request):
        """إضافة عنوان جديد"""
        serializer = CustomerAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(customer=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CustomerAddressDetailView(APIView):
    permission_classes = [IsCustomer]

    def get_object(self, request, address_id):
        try:
            return CustomerAddress.objects.get(
                id=address_id,
                customer=request.user   # ← مينفعش يشوف عنوان حد تاني
            )
        except CustomerAddress.DoesNotExist:
            return None

    def patch(self, request, address_id):
        """تعديل عنوان"""
        address = self.get_object(request, address_id)
        if not address:
            return Response({'error': 'Address not found.'}, status=404)

        serializer = CustomerAddressSerializer(
            address, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, address_id):
        """حذف عنوان"""
        address = self.get_object(request, address_id)
        if not address:
            return Response({'error': 'Address not found.'}, status=404)
        address.delete()
        return Response({'message': 'Address deleted.'}, status=204)
    


from accounts.models import Provider
from accounts.permissions import IsCustomer
from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer, ProviderReviewsSerializer

class ReviewCreateView(APIView):
    permission_classes = [IsCustomerOrAdmin]

    def post(self, request):
        user_type = request.auth.payload.get('user_type')
        
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        provider = serializer.validated_data['provider']
        rating = serializer.validated_data['rating']

        # الأدمن لازم يبعت customer_id في الـ body
        if user_type == 'admin':
            customer_id = request.data.get('customer_id')
            if not customer_id:
                return Response(
                    {'error': 'customer_id is required for admin.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response({'error': 'Customer not found.'}, status=404)
        else:
            customer = request.user

        review = serializer.save(customer=customer)
        provider.update_rating(rating)
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
    

class ReviewUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=404)

        old_rating = review.rating
        serializer = ReviewCreateSerializer(
            review,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()

        # إعادة حساب المتوسط بأمان
        provider = review.provider
        if provider.total_reviews > 0:
            total = (provider.average_rating * provider.total_reviews) - old_rating + review.rating
            provider.average_rating = total / provider.total_reviews
        else:
            provider.average_rating = review.rating
            provider.total_reviews = 1

        provider.save(update_fields=['average_rating', 'total_reviews'])

        return Response(ReviewSerializer(review).data)

class ReviewDeleteView(APIView):
    permission_classes = [IsCustomerOrAdmin]  # ← بدل IsCustomer

    def delete(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=404)

        user_type = request.auth.payload.get('user_type')
        is_owner = str(review.customer_id) == str(request.user.id)
        is_admin = user_type == 'admin'

        if not is_owner and not is_admin:
            return Response({'error': 'Permission denied.'}, status=403)

        provider = review.provider
        rating = review.rating
        review.delete()
        self._recalculate_rating(provider, rating)
        return Response({'message': 'Review deleted successfully.'})

    def _recalculate_rating(self, provider, deleted_rating):
        if provider.total_reviews <= 1:
            provider.average_rating = 0.00
            provider.total_reviews = 0
        else:
            total = (provider.average_rating * provider.total_reviews) - deleted_rating
            provider.total_reviews -= 1
            provider.average_rating = total / provider.total_reviews
        provider.save(update_fields=['average_rating', 'total_reviews'])

class ProviderReviewsView(APIView):
    """GET /reviews/provider/<provider_id>/ — كل تقييمات فني + المتوسط"""
    permission_classes = []  # متاح للكل

    def get(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id, is_active=True)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        reviews = Review.objects.filter(provider=provider).select_related('customer')

        data = {
            'provider_id': provider.id,
            'provider_name': provider.name,
            'average_rating': provider.average_rating,
            'total_reviews': provider.total_reviews,
            'reviews': ReviewSerializer(reviews, many=True).data,
        }

        return Response(data, status=status.HTTP_200_OK)


class ReviewDeleteView(APIView):
    """DELETE /reviews/<review_id>/ — صاحب التقييم أو أدمن"""
    permission_classes = [IsCustomerOrAdmin]

    def delete(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response(
                {'error': 'Review not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # التحقق: صاحب التقييم بس اللي يحذفه (أو أدمن)
        is_owner = review.customer_id == request.user.id
        is_admin = request.auth.payload.get('user_type') == 'admin'

        if not is_owner and not is_admin:
            return Response(
                {'error': 'You do not have permission to delete this review.'},
                status=status.HTTP_403_FORBIDDEN
            )

        provider = review.provider
        rating = review.rating
        review.delete()

        # إعادة حساب المتوسط بعد الحذف
        self._recalculate_rating(provider, rating)

        return Response(
            {'message': 'Review deleted successfully.'},
            status=status.HTTP_200_OK
        )

    def _recalculate_rating(self, provider, deleted_rating):
        """بيعيد حساب المتوسط بعد حذف تقييم"""
        if provider.total_reviews <= 1:
            provider.average_rating = 0.00
            provider.total_reviews = 0
        else:
            total = (provider.average_rating * provider.total_reviews) - deleted_rating
            provider.total_reviews -= 1
            provider.average_rating = total / provider.total_reviews

        provider.save(update_fields=['average_rating', 'total_reviews'])


class ProviderReviewsDeleteAllView(APIView):
    """DELETE /reviews/provider/<provider_id>/all/ — أدمن بس"""
    permission_classes = [IsAdminUser]

    def delete(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        deleted_count, _ = Review.objects.filter(provider=provider).delete()

        # ريسيت تقييمات الفني
        provider.average_rating = 0.00
        provider.total_reviews = 0
        provider.save(update_fields=['average_rating', 'total_reviews'])

        return Response(
            {
                'message': f'All reviews deleted for provider {provider.name}.',
                'deleted_count': deleted_count,
            },
            status=status.HTTP_200_OK
        )
    
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from accounts.models import Provider
from accounts.permissions import IsProvider
from .models import PreviousWork
from .serializers import PreviousWorkSerializer


class PreviousWorkListCreateView(APIView):
    """
    GET  /previous-works/provider/<provider_id>/  — عرض أعمال فني (للعميل)
    POST /previous-works/                         — الفني يضيف عمل جديد
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsProviderOrAdmin()]
        return []  # GET متاح للكل

    def get(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response(
                {'error': 'Provider not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        works = PreviousWork.objects.filter(provider=provider)
        return Response(
            PreviousWorkSerializer(works, many=True).data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        
        # تحديد الـ provider
        if user_type == 'admin':
            provider_id = request.data.get('provider')
            if not provider_id:
                return Response({'error': 'provider id is required.'}, status=400)
            try:
                provider = Provider.objects.get(id=provider_id)
            except Provider.DoesNotExist:
                return Response({'error': 'Provider not found.'}, status=404)
        else:
            provider = request.user

        # الفرونت بيرفع على Cloudinary وبيبعت الـ URL جاهز
        media_url = request.data.get('media_url')
        media_type = request.data.get('media_type')
        
        if not media_url:
            return Response({'error': 'media_url is required.'}, status=400)
        
        if media_type not in ('image', 'video'):
            return Response({'error': 'media_type must be image or video.'}, status=400)

        serializer = PreviousWorkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(provider=provider)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PreviousWorkDetailView(APIView):
    """
    DELETE /previous-works/<work_id>/  — الفني أو الأدمن يحذف عمل
    """

    def get_permissions(self):
        user_type = getattr(self.request.auth, 'payload', {}).get('user_type')
        if user_type == 'admin':
            return [IsAdminUser()]
        return [IsProvider()]

    def get_object(self, work_id, provider):
        try:
            return PreviousWork.objects.get(id=work_id, provider=provider)
        except PreviousWork.DoesNotExist:
            return None

    def delete(self, request, work_id):
        user_type = request.auth.payload.get('user_type')

        if user_type == 'admin':
            # الأدمن يقدر يحذف أي عمل
            try:
                work = PreviousWork.objects.get(id=work_id)
            except PreviousWork.DoesNotExist:
                return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # الفني يحذف بتاعته بس
            work = self.get_object(work_id, request.user)
            if not work:
                return Response(
                    {'error': 'Work not found or not yours.'},
                    status=status.HTTP_404_NOT_FOUND
                )

        work.delete()
        return Response({'message': 'Deleted successfully.'}, status=status.HTTP_200_OK)
    
from .models import Specialization
from .serializers import SpecializationSerializer, SpecializationWriteSerializer

class SpecializationListView(APIView):
    """
    GET  — متاح للكل (لما الـ Provider يختار تخصصه)
    POST — أدمن بس
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get(self, request):
        specs = Specialization.objects.filter(is_active=True)
        return Response(SpecializationSerializer(specs, many=True).data)

    def post(self, request):
        serializer = SpecializationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        spec = serializer.save()
        return Response(
            SpecializationSerializer(spec).data,
            status=status.HTTP_201_CREATED
        )


class SpecializationDetailView(APIView):
    """PATCH / DELETE — أدمن بس"""
    permission_classes = [IsAdminUser]

    def get_object(self, spec_id):
        try:
            return Specialization.objects.get(id=spec_id)
        except Specialization.DoesNotExist:
            return None

    def patch(self, request, spec_id):
        spec = self.get_object(spec_id)
        if not spec:
            return Response({'error': 'Specialization not found.'}, status=404)
        serializer = SpecializationWriteSerializer(spec, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SpecializationSerializer(spec).data)

    def delete(self, request, spec_id):
        spec = self.get_object(spec_id)
        if not spec:
            return Response({'error': 'Specialization not found.'}, status=404)
        spec.delete()
        return Response({'message': 'Deleted successfully.'}, status=204)
    
from django.db.models import Avg, Count

class ProviderReviewsView(APIView):
    permission_classes = []

    def get(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=404)

        reviews = Review.objects.filter(provider=provider).select_related('customer')
        
        result = reviews.aggregate(avg=Avg('rating'), count=Count('id'))
        avg = round(result['avg'] or 0, 2)
        total = result['count'] or 0

        # آبديت الـ provider بالقيم الجديدة
        provider.average_rating = avg
        provider.total_reviews = total
        provider.save(update_fields=['average_rating', 'total_reviews'])

        serializer = ProviderReviewsSerializer({
            'provider_id': provider.id,
            'provider_name': provider.name,
            'average_rating': avg,
            'total_reviews': total,
            'reviews': reviews,
        })

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class AdminCustomerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        is_active = request.query_params.get('is_active')
        customers = Customer.objects.all().order_by('-created_at')

        if is_active == 'true':
            customers = customers.filter(is_active=True)
        elif is_active == 'false':
            customers = customers.filter(is_active=False)

        serializer = CustomerAdminSerializer(customers, many=True)
        return Response(serializer.data)


class AdminCustomerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=404)
        return Response(CustomerAdminSerializer(customer).data)

    def patch(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=404)
        serializer = CustomerUpdateSerializer(customer, data=request.data, partial=True,
                                              context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CustomerAdminSerializer(customer).data)

    def delete(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=404)
        customer.is_active = False
        customer.save(update_fields=['is_active'])
        return Response({'message': 'Customer deactivated.'})
    

# City & Region Views
class CityListView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get(self, request):
        cities = City.objects.filter(is_active=True)
        return Response(CitySerializer(cities, many=True).data)

    def post(self, request):
        serializer = CityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = serializer.save()
        return Response(CitySerializer(city).data, status=status.HTTP_201_CREATED)


class CityDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, city_id):
        try:
            return City.objects.get(id=city_id)
        except City.DoesNotExist:
            return None

    def patch(self, request, city_id):
        city = self.get_object(city_id)
        if not city:
            return Response({'error': 'City not found.'}, status=404)
        serializer = CityWriteSerializer(city, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CitySerializer(city).data)

    def delete(self, request, city_id):
        city = self.get_object(city_id)
        if not city:
            return Response({'error': 'City not found.'}, status=404)
        city.delete()
        return Response({'message': 'City deleted.'}, status=204)


class RegionListView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get(self, request):
        city_id = request.query_params.get('city_id')
        regions = Region.objects.filter(is_active=True)
        if city_id:
            regions = regions.filter(city_id=city_id)
        return Response(RegionWriteSerializer(regions, many=True).data)

    def post(self, request):
        serializer = RegionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        region = serializer.save()
        return Response(RegionWriteSerializer(region).data, status=status.HTTP_201_CREATED)


class RegionDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, region_id):
        try:
            return Region.objects.get(id=region_id)
        except Region.DoesNotExist:
            return None

    def patch(self, request, region_id):
        region = self.get_object(region_id)
        if not region:
            return Response({'error': 'Region not found.'}, status=404)
        serializer = RegionWriteSerializer(region, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RegionWriteSerializer(region).data)

    def delete(self, request, region_id):
        region = self.get_object(region_id)
        if not region:
            return Response({'error': 'Region not found.'}, status=404)
        region.delete()
        return Response({'message': 'Region deleted.'}, status=204)


# ProviderAddress Views
class ProviderAddressView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        addresses = ProviderAddress.objects.filter(provider=request.user)
        return Response(ProviderAddressSerializer(addresses, many=True).data)

    def post(self, request):
        serializer = ProviderAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(provider=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProviderAddressDetailView(APIView):
    permission_classes = [IsProvider]

    def get_object(self, request, address_id):
        try:
            return ProviderAddress.objects.get(
                id=address_id,
                provider=request.user
            )
        except ProviderAddress.DoesNotExist:
            return None

    def patch(self, request, address_id):
        address = self.get_object(request, address_id)
        if not address:
            return Response({'error': 'Address not found.'}, status=404)
        serializer = ProviderAddressSerializer(
            address, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, address_id):
        address = self.get_object(request, address_id)
        if not address:
            return Response({'error': 'Address not found.'}, status=404)
        address.delete()
        return Response({'message': 'Address deleted.'}, status=204)
    
# في views.py
class AdminProviderAddressView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, provider_id):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=404)
        
        serializer = ProviderAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(provider=provider)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminProviderAddressDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, provider_id, address_id):
        try:
            address = ProviderAddress.objects.get(id=address_id, provider_id=provider_id)
        except ProviderAddress.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=404)
        
        serializer = ProviderAddressSerializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, provider_id, address_id):
        try:
            address = ProviderAddress.objects.get(id=address_id, provider_id=provider_id)
        except ProviderAddress.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=404)
        
        address.delete()
        return Response({'message': 'Address deleted.'}, status=204)
    
from math import radians, sin, cos, sqrt, atan2

class NearbyProvidersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # جيب الـ params من الـ request
        try:
            user_lat = float(request.query_params.get('lat'))
            user_lng = float(request.query_params.get('lng'))
            radius   = float(request.query_params.get('radius', 10))  # default 10km
        except (TypeError, ValueError):
            return Response(
                {'error': 'lat and lng are required as valid numbers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # جيب كل الـ providers اللي عندهم عنوان بـ lat/lng
        addresses = ProviderAddress.objects.filter(
            lat__isnull=False,
            lng__isnull=False,
            provider__is_active=True,
            provider__is_approved=True,
        ).select_related('provider')

        results = []
        for address in addresses:
            distance = self._haversine(
                user_lat, user_lng,
                float(address.lat), float(address.lng)
            )
            if distance <= radius:
                results.append({
                    'provider_id':    address.provider.id,
                    'provider_name':  address.provider.name,
                    'specialization': address.provider.specialization.name if address.provider.specialization else None,
                    'average_rating': address.provider.average_rating,
                    'total_reviews':  address.provider.total_reviews,
                    'distance_km':    round(distance, 2),
                    'address': {
                        'city':    address.city.name if address.city else None,
                        'region':  address.region.name if address.region else None,
                        'district': address.district,
                        'lat':     address.lat,
                        'lng':     address.lng,
                    }
                })

        # رتب من الأقرب للأبعد
        results.sort(key=lambda x: x['distance_km'])

        return Response(results, status=status.HTTP_200_OK)

    def _haversine(self, lat1, lng1, lat2, lng2):
        """بيحسب المسافة بالكيلومتر بين نقطتين"""
        R = 6371  # نصف قطر الأرض بالكيلومتر
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))