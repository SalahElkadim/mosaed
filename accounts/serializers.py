# accounts/serializers.py

from rest_framework import serializers
from django.utils import timezone
from .models import Admin, Customer, Provider, OTPVerification, BiometricToken, CustomerAddress,Specialization,Region,City,ProviderAddress


# ==================== ADMIN ====================

class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['id', 'name', 'email', 'phone_number',
                  'role', 'custom_permissions', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


# ==================== CUSTOMER ====================
class SpecializationSerializer(serializers.ModelSerializer):
    providers_count = serializers.IntegerField(source='providers.count', read_only=True)

    class Meta:
        model  = Specialization
        fields = ['id', 'name', 'description', 'is_active', 'providers_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class SpecializationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Specialization
        fields = ['name', 'description', 'is_active']

    def validate_name(self, value):
        qs = Specialization.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This specialization already exists.")
        return value.strip()
    
class CustomerRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['name', 'phone_number', 'email']  # ✅ address اتحذف

    def validate_phone_number(self, value):
        if Customer.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

# CustomerAddress بعد التعديل
class CustomerAddressSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = CustomerAddress
        fields = ['id', 'city', 'city_name', 'region', 'region_name',
                  'district', 'street', 'building_no', 'floor_no',
                  'apartment_no', 'label', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        city = attrs.get('city')
        region = attrs.get('region')
        # التأكد إن الـ region تابعة للـ city
        if city and region and region.city != city:
            raise serializers.ValidationError(
                "This region does not belong to the selected city."
            )
        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_number', 'email',
                  'addresses', 'is_phone_verified', 'created_at']
        read_only_fields = ['id', 'is_phone_verified', 'created_at']


class CustomerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['name', 'email']  # ✅ address اتحذف

    def validate_email(self, value):
        user = self.context['request'].user
        if Customer.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value


# ==================== PROVIDER ====================

class ProviderRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ['name', 'phone_number', 'email', 
                  'specialization',
                  'national_id', 'commercial_registration', 'contract_image']

    def validate_phone_number(self, value):
        if Provider.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def validate(self, attrs):
        if not attrs.get('national_id') and not attrs.get('commercial_registration'):
            raise serializers.ValidationError(
                "Either national ID or commercial registration is required."
            )
        return attrs

class ProviderAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ['name', 'email', 'city', 
                  'district', 'is_approved', 'is_active']

from rest_framework import serializers
from .models import PreviousWork


class PreviousWorkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreviousWork
        fields = ['id', 'title', 'description',
            'media_type', 'media_url', 'thumbnail_url', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_media_type(self, value):
        if value not in ('image', 'video'):
            raise serializers.ValidationError("media_type must be 'image' or 'video'.")
        return value

    def validate(self, attrs):
        # الفيديو لازم يكون عنده thumbnail
        if attrs.get('media_type') == 'video' and not attrs.get('thumbnail_url'):
            raise serializers.ValidationError(
                "thumbnail_url is required for videos."
            )
        return attrs

class ProviderAddressSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = ProviderAddress
        fields = ['id', 'city', 'city_name', 'region', 'region_name',
                  'district', 'street', 'building_no',          # ← district أضفناه
                  'label', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        city = attrs.get('city')
        region = attrs.get('region')
        if city and region and region.city != city:
            raise serializers.ValidationError(
                "This region does not belong to the selected city."
            )
        return attrs
    
class ProviderSerializer(serializers.ModelSerializer):
    previous_works = PreviousWorkSerializer(many=True, read_only=True)
    specialization = SpecializationSerializer(read_only=True)
    addresses = ProviderAddressSerializer(many=True, read_only=True)   # ← أضفناه

    class Meta:
        model = Provider
        fields = ['id', 'name', 'phone_number', 'email', 
                'specialization', 'addresses',                        # ← address القديم وعناوين جديدة
                'total_services', 'average_rating', 'total_reviews',
                'is_phone_verified', 'is_approved', 'is_active',
                'previous_works', 'created_at']

class ProviderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ['name', 'email', ]    
    def validate_email(self, value):
        qs = Provider.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

class ProviderAdminSerializer(serializers.ModelSerializer):
    specialization = SpecializationSerializer(read_only=True)
    addresses = ProviderAddressSerializer(many=True, read_only=True)   # ← أضفناه

    class Meta:
        model = Provider
        fields = ['id', 'name', 'phone_number', 'email', 
                  'specialization', 'addresses',                        # ← عدلناه
                  'national_id', 'commercial_registration', 'contract_image',
                  'wallet_balance', 'total_services', 'average_rating', 'total_reviews',
                  'is_phone_verified', 'is_approved', 'is_active', 'created_at', 'last_login']
        read_only_fields = fields


# ==================== OTP ====================

class SendOTPSerializer(serializers.Serializer):
    USER_TYPE_CHOICES = [('customer', 'Customer'), ('provider', 'Provider')]
    phone_number = serializers.CharField(max_length=20)
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)

    def validate_phone_number(self, value):
        return value.strip()


class VerifyOTPSerializer(serializers.Serializer):
    USER_TYPE_CHOICES = [('customer', 'Customer'), ('provider', 'Provider')]
    phone_number = serializers.CharField(max_length=20)
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    otp_code = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        user_type = attrs.get('user_type')
        otp_code = attrs.get('otp_code')

        otp = OTPVerification.objects.filter(
            phone_number=phone_number,
            user_type=user_type,
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            raise serializers.ValidationError("No OTP found for this number.")

        otp.attempts += 1
        otp.save(update_fields=['attempts'])

        if not otp.is_valid():
            raise serializers.ValidationError("OTP is expired or max attempts reached.")

        if otp.code != otp_code:
            raise serializers.ValidationError("Invalid OTP code.")

        attrs['otp'] = otp
        return attrs


# ==================== BIOMETRIC ====================

class RegisterBiometricSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=255)


class BiometricLoginSerializer(serializers.Serializer):
    biometric_token = serializers.CharField(max_length=128)
    device_id = serializers.CharField(max_length=255)

    def validate(self, attrs):
        try:
            biometric = BiometricToken.objects.get(
                token=attrs.get('biometric_token'),
                device_id=attrs.get('device_id'),
                is_active=True
            )
            if not biometric.is_valid():
                raise serializers.ValidationError("Biometric token expired. Please login with OTP.")
        except BiometricToken.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired biometric token.")

        attrs['biometric'] = biometric
        return attrs
    
# reviews/serializers.py
from rest_framework import serializers
from .models import Review

class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['provider', 'rating', 'comment']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user_type = getattr(request.auth, 'payload', {}).get('user_type') if request else None
        
        # الأدمن مش محتاج الـ unique check
        if user_type == 'admin':
            return attrs

        customer = request.user
        provider = attrs.get('provider')
        if provider and Review.objects.filter(customer=customer, provider=provider).exists():
            raise serializers.ValidationError("You have already reviewed this provider.")
        return attrs

class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'customer_name', 'rating', 'comment', 'created_at']
        read_only_fields = fields


class ProviderReviewsSerializer(serializers.Serializer):
    provider_id = serializers.UUIDField()
    provider_name = serializers.CharField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_reviews = serializers.IntegerField()
    reviews = ReviewSerializer(many=True)

class CustomerAdminSerializer(serializers.ModelSerializer):
    addresses       = CustomerAddressSerializer(many=True, read_only=True)
    bookings_count  = serializers.IntegerField(source='bookings.count', read_only=True)

    class Meta:
        model  = Customer
        fields = ['id', 'name', 'phone_number', 'email',
                  'is_phone_verified', 'is_active',
                  'addresses', 'bookings_count', 'created_at', 'last_login']
        read_only_fields = fields

# City & Region
class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'name', 'city', 'is_active']

class CitySerializer(serializers.ModelSerializer):
    regions = RegionSerializer(many=True, read_only=True)

    class Meta:
        model = City
        fields = ['id', 'name', 'is_active', 'regions']

class CityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['name', 'is_active']

class RegionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'name', 'city', 'is_active']  # ← ضيف 'id'
        read_only_fields = ['id']

    def validate(self, attrs):
        city = attrs.get('city')
        name = attrs.get('name')
        qs = Region.objects.filter(name__iexact=name, city=city)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This region already exists in this city."
            )
        return attrs


