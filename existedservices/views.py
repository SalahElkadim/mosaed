from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from accounts.permissions import IsCustomer,IsProviderOrAdmin   
from .models import ExistedService, ServiceAttribute, PreviousWork,Booking, ServiceReview, ServiceProvider, Warranty
from utils.cloudinary import upload_image, upload_video
from .serializers import (
    # Service
    ExistedServiceListSerializer,
    ExistedServiceDetailSerializer,
    ExistedServiceAdminListSerializer,PreviousWorkSerializer,
    ExistedServiceAdminDetailSerializer,
    ExistedServiceWriteSerializer,WarrantyWriteSerializer,PreviousWorkWriteSerializer,ProviderCompletionFormListSerializer,
    # Attribute
    ServiceAttributeAdminSerializer,
    ServiceAttributeWriteSerializer,
    # Booking
    BookingCreateSerializer,
    BookingSerializer,
    BookingCancelSerializer,
    BookingAdminSerializer,
    BookingStatusUpdateSerializer,ServiceReviewCreateSerializer,
    ServiceReviewSerializer, ServiceRatingSummarySerializer,
    ServiceProviderAdminSerializer,  # Added missing import
    AssignProviderSerializer,  # Added missing import
    ServiceProviderSerializer, ServiceCompletionFormSerializer,
    ServiceCompletionFormUpdateSerializer,
    CompletionMediaWriteSerializer, CompletionMediaSerializer, # Added missing import
)
from .models import ServiceCompletionForm, CompletionMedia

from django.db.models import Avg, Count
import base64
import uuid as uuid_lib
from django.core.files.base import ContentFile


def _decode_base64_file(raw_value, default_ext='jpg'):
    """بيحول base64 string (مع أو من غير data URI) لـ ContentFile قابل للرفع."""
    if ';base64,' in raw_value:
        header, raw_value = raw_value.split(';base64,', 1)
        ext = header.split('/')[-1] if '/' in header else default_ext
    else:
        ext = default_ext

    try:
        decoded = base64.b64decode(raw_value)
    except (TypeError, ValueError, base64.binascii.Error):
        raise ValueError("صيغة الملف (base64) غير صحيحة.")

    return ContentFile(decoded, name=f"{uuid_lib.uuid4()}.{ext}")


def _resolve_media_upload(request, field_name, media_type, folder):
    """
    بيرجع (media_url, thumbnail_url) لأي media (image/video)، سواء جاي:
    - multipart:  request.FILES[field_name]
    - base64:     request.data[field_name] كـ string base64 (مش بادئ بـ http)
    بيرجع (None, None) لو مفيش حاجة اتبعتت خالص.
    """
    file_obj = None

    if field_name in request.FILES:
        file_obj = request.FILES[field_name]
    else:
        raw_value = request.data.get(field_name)
        if raw_value and isinstance(raw_value, str) and not raw_value.startswith('http'):
            default_ext = 'mp4' if media_type == 'video' else 'jpg'
            file_obj = _decode_base64_file(raw_value, default_ext=default_ext)

    if file_obj is None:
        return None, None

    if media_type == 'video':
        result = upload_video(file_obj, folder=folder)
        return result['url'], result['thumbnail']
    else:
        return upload_image(file_obj, folder=folder), None
# ==================== CLIENT - SERVICE VIEWS ====================

class ExistedServiceListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        services = ExistedService.objects.filter(is_active=True)
        serializer = ExistedServiceListSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExistedServiceDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id, is_active=True)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found..'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExistedServiceDetailSerializer(service).data, status=status.HTTP_200_OK)


# ==================== ADMIN - SERVICE VIEWS ====================

class AdminExistedServiceListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        is_active = request.query_params.get('is_active')
        services  = ExistedService.objects.all()

        if is_active == 'true':
            services = services.filter(is_active=True)
        elif is_active == 'false':
            services = services.filter(is_active=False)

        return Response(ExistedServiceAdminListSerializer(services, many=True).data)

    def post(self, request):
        data = request.data.copy()

        if 'image' in request.FILES:
            data['image'] = upload_image(
                request.FILES['image'],
                folder="services"
            )

        serializer = ExistedServiceWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        return Response(
            ExistedServiceAdminDetailSerializer(service).data,
            status=status.HTTP_201_CREATED
        )


class AdminExistedServiceDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, service_id):
        try:
            return ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return None

    def get(self, request, service_id):
        service = self.get_object(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExistedServiceAdminDetailSerializer(service).data)

    def patch(self, request, service_id):
        service = self.get_object(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()

        if 'image' in request.FILES:
            data['image'] = upload_image(
                request.FILES['image'],
                folder="services"
            )

        serializer = ExistedServiceWriteSerializer(service, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ExistedServiceAdminDetailSerializer(service).data)

    def delete(self, request, service_id):
        service = self.get_object(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
        service.delete()
        return Response({'message': 'Service deleted successfully.'}, status=status.HTTP_200_OK)


# ==================== ADMIN - ATTRIBUTE VIEWS ====================

class AdminServiceAttributeListView(APIView):
    permission_classes = [IsAdminUser]

    def get_service(self, service_id):
        try:
            return ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return None

    def get(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ServiceAttributeAdminSerializer(service.attributes.all(), many=True).data)

    def post(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ServiceAttributeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attribute = serializer.save(service=service)
        return Response(
            ServiceAttributeAdminSerializer(attribute).data,
            status=status.HTTP_201_CREATED
        )


class AdminServiceAttributeDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, service_id, attribute_id):
        try:
            return ServiceAttribute.objects.get(id=attribute_id, service_id=service_id)
        except ServiceAttribute.DoesNotExist:
            return None

    def patch(self, request, service_id, attribute_id):
        attribute = self.get_object(service_id, attribute_id)
        if not attribute:
            return Response({'error': 'Attribute not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ServiceAttributeWriteSerializer(attribute, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ServiceAttributeAdminSerializer(attribute).data)

    def delete(self, request, service_id, attribute_id):
        attribute = self.get_object(service_id, attribute_id)
        if not attribute:
            return Response({'error': 'Attribute not found.'}, status=status.HTTP_404_NOT_FOUND)
        attribute.delete()
        return Response({'message': 'Attribute deleted successfully.'}, status=status.HTTP_200_OK)


# ==================== CLIENT - BOOKING VIEWS ====================

class CustomerBookingListView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        status_filter = request.query_params.get('status')
        bookings = Booking.objects.filter(customer=request.user)

        if status_filter in ('pending', 'confirmed', 'completed', 'cancelled'):
            bookings = bookings.filter(status=status_filter)

        return Response(BookingSerializer(bookings, many=True).data)

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class CustomerBookingDetailView(APIView):
    permission_classes = [IsCustomer]

    def get_object(self, request, booking_id):
        try:
            return Booking.objects.get(id=booking_id, customer=request.user)
        except Booking.DoesNotExist:
            return None

    def get(self, request, booking_id):
        booking = self.get_object(request, booking_id)
        if not booking:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BookingSerializer(booking).data)

    def post(self, request, booking_id):
        """إلغاء الحجز"""
        booking = self.get_object(request, booking_id)
        if not booking:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingCancelSerializer(data={}, context={'booking': booking})
        serializer.is_valid(raise_exception=True)

        booking.status = 'cancelled'
        booking.save(update_fields=['status'])
        return Response(BookingSerializer(booking).data)


# ==================== ADMIN - BOOKING VIEWS ====================

class AdminBookingListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter   = request.query_params.get('status')
        service_filter  = request.query_params.get('service_id')
        customer_filter = request.query_params.get('customer_id')  # ← جديد

        bookings = Booking.objects.select_related(
            'customer', 'service'
        ).prefetch_related('items__attribute')

        if status_filter in ('pending', 'confirmed', 'completed', 'cancelled'):
            bookings = bookings.filter(status=status_filter)
        if service_filter:
            bookings = bookings.filter(service_id=service_filter)
        if customer_filter:                                         # ← جديد
            bookings = bookings.filter(customer_id=customer_filter)

        return Response(BookingAdminSerializer(bookings, many=True).data)
    
class AdminBookingDetailView(APIView):
    permission_classes = [IsProviderOrAdmin]

    def get_object(self, booking_id):
        try:
            return Booking.objects.select_related(
                'customer', 'service'
            ).prefetch_related('items__attribute').get(id=booking_id)
        except Booking.DoesNotExist:
            return None

    def get(self, request, booking_id):
        booking = self.get_object(booking_id)
        if not booking:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BookingAdminSerializer(booking).data)


class AdminBookingStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingStatusUpdateSerializer(
            data=request.data,
            context={'booking': booking}
        )
        serializer.is_valid(raise_exception=True)
        booking.status = serializer.validated_data['status']
        booking.save(update_fields=['status'])
        return Response(BookingAdminSerializer(booking).data)
    
class ServiceReviewListView(APIView):
    """
    GET  → عرض كل التقييمات لخدمة معينة (public)
    POST → إضافة/تعديل تقييم (customer فقط)
    """
 
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsCustomer()]
        return [AllowAny()]
 
    def get_service(self, service_id):
        try:
            return ExistedService.objects.get(id=service_id, is_active=True)
        except ExistedService.DoesNotExist:
            return None
 
    def get(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        reviews = service.reviews.select_related('customer').all()
        return Response(ServiceReviewSerializer(reviews, many=True).data)
 
    def post(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        serializer = ServiceReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'service': service}
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(ServiceReviewSerializer(review).data, status=status.HTTP_201_CREATED)
 
 
class ServiceRatingSummaryView(APIView):
    """
    GET /services/<service_id>/rating/
    يرجع متوسط النجوم + توزيع التقييمات
    """
    permission_classes = [AllowAny]
 
    def get(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id, is_active=True)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        reviews = service.reviews.all()
 
        aggregate = reviews.aggregate(
            average_stars=Avg('stars'),
            total_reviews=Count('id')
        )
 
        # توزيع النجوم 1 → 5
        breakdown = {}
        for i in range(1, 6):
            breakdown[str(i)] = reviews.filter(stars=i).count()
 
        data = {
            'service_id':    str(service.id),
            'service_title': service.title,
            'average_stars': round(aggregate['average_stars'] or 0, 2),
            'total_reviews': aggregate['total_reviews'],
            'stars_breakdown': breakdown,
        }
        return Response(data, status=status.HTTP_200_OK)
 
 
class AdminReviewDeleteView(APIView):
    """
    DELETE /reviews/<review_id>/
    حذف تقييم واحد (admin فقط)
    """
    permission_classes = [IsAdminUser]
 
    def delete(self, request, review_id):
        try:
            review = ServiceReview.objects.get(id=review_id)
        except ServiceReview.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        review.delete()
        return Response({'message': 'Review deleted successfully.'}, status=status.HTTP_200_OK)
 
 
class AdminServiceReviewsClearView(APIView):
    """
    DELETE /services/<service_id>/reviews/clear/
    حذف كل تقييمات خدمة معينة (admin فقط)
    """
    permission_classes = [IsAdminUser]
 
    def delete(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        deleted_count, _ = service.reviews.all().delete()
        return Response(
            {'message': f'{deleted_count} review(s) deleted successfully.'},
            status=status.HTTP_200_OK
        )
    

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
# from accounts.permissions import IsCustomer
# from .models import ExistedService, ServiceProvider
# from .serializers import (
#     ServiceProviderSerializer,
#     ServiceProviderAdminSerializer,
#     AssignProviderSerializer,
# )
 
 
# ----------------------------------------------------------
# Endpoints الجديدة:
#
# GET  /services/<id>/providers/              → الفنيين المتاحين للعميل (public)
# GET  /admin/services/<id>/providers/        → كل الفنيين للأدمن
# POST /admin/services/<id>/providers/        → إضافة فني للخدمة (admin)
# PATCH/DELETE /admin/services/<id>/providers/<sp_id>/  → تعديل أو حذف (admin)
# ----------------------------------------------------------
 
 
class ServiceProviderListView(APIView):
    """
    GET /services/<service_id>/providers/
    للعميل — يشوف الفنيين المتاحين قبل الحجز
    """
    permission_classes = [AllowAny]
 
    def get(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id, is_active=True)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        providers = service.service_providers.filter(
            is_available=True,
            provider__is_active=True,
            provider__is_approved=True
        ).select_related('provider')
 
        return Response(ServiceProviderSerializer(providers, many=True).data)
 
 
class AdminServiceProviderListView(APIView):
    """
    GET  /admin/services/<service_id>/providers/  → كل الفنيين (بغض النظر عن availability)
    POST /admin/services/<service_id>/providers/  → إضافة فني
    """
    permission_classes = [IsAdminUser]
 
    def get_service(self, service_id):
        try:
            return ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return None
 
    def get(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        providers = service.service_providers.select_related('provider').all()
        return Response(ServiceProviderAdminSerializer(providers, many=True).data)
 
    def post(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        serializer = AssignProviderSerializer(
            data=request.data,
            context={'service': service}
        )
        serializer.is_valid(raise_exception=True)
        sp = serializer.save()
        return Response(
            ServiceProviderAdminSerializer(sp).data,
            status=status.HTTP_201_CREATED
        )
 
 
class AdminServiceProviderDetailView(APIView):
    """
    PATCH  /admin/services/<service_id>/providers/<sp_id>/  → تغيير is_available
    DELETE /admin/services/<service_id>/providers/<sp_id>/  → إزالة الفني من الخدمة
    """
    permission_classes = [IsAdminUser]
 
    def get_object(self, service_id, sp_id):
        try:
            return ServiceProvider.objects.get(id=sp_id, service_id=service_id)
        except ServiceProvider.DoesNotExist:
            return None
 
    def patch(self, request, service_id, sp_id):
        sp = self.get_object(service_id, sp_id)
        if not sp:
            return Response({'error': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        is_available = request.data.get('is_available')
        if is_available is None:
            return Response(
                {'error': 'is_available field is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(is_available, bool):
            return Response(
                {'error': 'is_available must be true or false.'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        sp.is_available = is_available
        sp.save(update_fields=['is_available'])
        return Response(ServiceProviderAdminSerializer(sp).data)
 
    def delete(self, request, service_id, sp_id):
        sp = self.get_object(service_id, sp_id)
        if not sp:
            return Response({'error': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        sp.delete()
        return Response(
            {'message': 'Provider removed from service successfully.'},
            status=status.HTTP_200_OK
        )
 
# ==================== ADMIN - WARRANTY VIEWS ====================

class AdminServiceWarrantyView(APIView):
    """
    GET    /admin/services/<service_id>/warranty/  → عرض الضمان
    POST   /admin/services/<service_id>/warranty/  → إنشاء ضمان
    PATCH  /admin/services/<service_id>/warranty/  → تعديل الضمان
    DELETE /admin/services/<service_id>/warranty/  → حذف الضمان
    """
    permission_classes = [IsAdminUser]

    def get_service(self, service_id):
        try:
            return ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return None

    def get(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            warranty = service.warranty
        except Warranty.DoesNotExist:
            return Response({'error': 'No warranty for this service.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(WarrantyWriteSerializer(warranty).data)

    def post(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        # الخدمة عندها ضمان بالفعل؟
        if hasattr(service, 'warranty'):
            return Response(
                {'error': 'Warranty already exists. Use PATCH to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WarrantyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warranty = serializer.save(service=service)
        return Response(WarrantyWriteSerializer(warranty).data, status=status.HTTP_201_CREATED)

    def patch(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            warranty = service.warranty
        except Warranty.DoesNotExist:
            return Response({'error': 'No warranty found. Use POST to create.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WarrantyWriteSerializer(warranty, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WarrantyWriteSerializer(warranty).data)

    def delete(self, request, service_id):
        service = self.get_service(service_id)
        if not service:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            warranty = service.warranty
        except Warranty.DoesNotExist:
            return Response({'error': 'No warranty found.'}, status=status.HTTP_404_NOT_FOUND)

        warranty.delete()
        return Response({'message': 'Warranty deleted successfully.'}, status=status.HTTP_200_OK)
    

class ProviderCompletionFormView(APIView):
    permission_classes = [IsProviderOrAdmin]

    def get_object(self, request, booking_id):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                # الأدمن يشوف أي نموذج
                return ServiceCompletionForm.objects.get(booking__id=booking_id)
            else:
                # الفني بتاع الحجز بس
                return ServiceCompletionForm.objects.get(
                    booking__id=booking_id,
                    booking__provider=request.user
                )
        except ServiceCompletionForm.DoesNotExist:
            return None

    def get(self, request, booking_id):
        form = self.get_object(request, booking_id)
        if not form:
            return Response(
                {'error': 'Completion form not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(ServiceCompletionFormSerializer(form).data)

    def patch(self, request, booking_id):
        form = self.get_object(request, booking_id)
        if not form:
            return Response(
                {'error': 'Completion form not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ServiceCompletionFormUpdateSerializer(
            form, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ServiceCompletionFormSerializer(form).data)


class ProviderCompletionMediaView(APIView):
    permission_classes = [IsProviderOrAdmin]

    def get_form(self, request, booking_id):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                return ServiceCompletionForm.objects.get(booking__id=booking_id)
            else:
                return ServiceCompletionForm.objects.get(
                    booking__id=booking_id,
                    booking__provider=request.user
                )
        except ServiceCompletionForm.DoesNotExist:
            return None

    def post(self, request, booking_id):
        form = self.get_form(request, booking_id)
        if not form:
            return Response({'error': 'Completion form not found.'}, status=status.HTTP_404_NOT_FOUND)
        if form.is_finished:
            return Response({'error': 'Cannot add media to a finished form.'}, status=status.HTTP_400_BAD_REQUEST)

        media_type = request.data.get('media_type')
        if media_type not in ('image', 'video'):
            return Response({'error': 'media_type must be image or video.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            media_url, thumbnail_url = _resolve_media_upload(
                request, field_name='media', media_type=media_type, folder="completion_media"
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not media_url:
            return Response({'error': 'media file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['media_url']     = media_url
        data['thumbnail_url'] = thumbnail_url

        serializer = CompletionMediaWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        media = serializer.save(form=form)
        return Response(CompletionMediaSerializer(media).data, status=status.HTTP_201_CREATED)

    def delete(self, request, booking_id, media_id):
        form = self.get_form(request, booking_id)
        if not form:
            return Response(
                {'error': 'Completion form not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if form.is_finished:
            return Response(
                {'error': 'Cannot delete media from a finished form.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            media = CompletionMedia.objects.get(id=media_id, form=form)
        except CompletionMedia.DoesNotExist:
            return Response(
                {'error': 'Media not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        media.delete()
        return Response({'message': 'Media deleted successfully.'}, status=status.HTTP_200_OK)
    """
    GET /admin/completion-forms/<booking_id>/  → الأدمن يشوف النموذج
    """
    permission_classes = [IsAdminUser]

    def get(self, request, booking_id):
        try:
            form = ServiceCompletionForm.objects.get(booking__id=booking_id)
        except ServiceCompletionForm.DoesNotExist:
            return Response(
                {'error': 'Completion form not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(ServiceCompletionFormSerializer(form).data)
    
from .models import Coupon
from .serializers import (
    CouponAdminSerializer,
    CouponWriteSerializer,
    CouponValidateSerializer,
    CouponSerializer,  # Added missing import
)

# ==================== CLIENT - COUPON VALIDATE ====================

class CouponValidateView(APIView):
    """
    POST /coupons/validate/
    العميل يتحقق من الكوبون ويشوف الخصم قبل الحجز
    """
    permission_classes = [IsCustomer]

    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        coupon     = serializer.validated_data['coupon']
        total_cost = serializer.validated_data['total_cost']
        discount   = coupon.calc_discount(total_cost)

        return Response({
            'coupon':          CouponSerializer(coupon).data,
            'original_cost':   total_cost,
            'discount_amount': discount,
            'final_cost':      round(total_cost - discount, 2),
        })


# ==================== ADMIN - COUPON VIEWS ====================

class AdminCouponListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        is_active = request.query_params.get('is_active')
        coupons   = Coupon.objects.all()

        if is_active == 'true':
            coupons = coupons.filter(is_active=True)
        elif is_active == 'false':
            coupons = coupons.filter(is_active=False)

        return Response(CouponAdminSerializer(coupons, many=True).data)

    def post(self, request):
        serializer = CouponWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.save()
        return Response(
            CouponAdminSerializer(coupon).data,
            status=status.HTTP_201_CREATED
        )


class AdminCouponDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, coupon_id):
        try:
            return Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            return None

    def get(self, request, coupon_id):
        coupon = self.get_object(coupon_id)
        if not coupon:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CouponAdminSerializer(coupon).data)

    def patch(self, request, coupon_id):
        coupon = self.get_object(coupon_id)
        if not coupon:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CouponWriteSerializer(coupon, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CouponAdminSerializer(coupon).data)

    def delete(self, request, coupon_id):
        coupon = self.get_object(coupon_id)
        if not coupon:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)
        coupon.delete()
        return Response({'message': 'Coupon deleted.'}, status=status.HTTP_200_OK)
    

class AdminAvailableProvidersForServiceView(APIView):
    """
    GET /admin/services/<service_id>/available-providers/
    يجيب الفنيين اللي عندهم نفس تخصص الخدمة ومش متعينين فيها
    """
    permission_classes = [IsAdminUser]

    def get(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        # الفنيين اللي متعينين بالفعل في الخدمة دي
        assigned_ids = ServiceProvider.objects.filter(
            service=service
        ).values_list('provider_id', flat=True)

        from accounts.models import Provider
        providers = Provider.objects.filter(
            is_active=True,
            is_approved=True,
        ).exclude(id__in=assigned_ids)

        # لو الخدمة عندها تخصص، فلتر بيه
        if service.specialization:
            providers = providers.filter(specialization=service.specialization)

        data = [
            {
                'id': str(p.id),
                'name': p.name,
                'phone_number': p.phone_number,
                'specialization': p.specialization.name if p.specialization else None,
            }
            for p in providers
        ]
        return Response(data)
    

class AdminBookingAssignProviderView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=404)

        provider_id = request.data.get('provider_id')
        if not provider_id:
            return Response({'error': 'provider_id is required.'}, status=400)

        from accounts.models import Provider
        try:
            provider = Provider.objects.get(id=provider_id, is_active=True, is_approved=True)
        except Provider.DoesNotExist:
            return Response({'error': 'Provider not found.'}, status=404)

        booking.provider = provider
        booking.save(update_fields=['provider'])
        return Response(BookingAdminSerializer(booking).data)
    

# ==================== PREVIOUS WORK VIEWS ====================

class ServicePreviousWorksView(APIView):
    """
    GET /services/<service_id>/previous-works/
    العميل يشوف الأعمال السابقة للخدمة (قبل/بعد)
    """
    permission_classes = [AllowAny]

    def get(self, request, service_id):
        try:
            service = ExistedService.objects.get(id=service_id, is_active=True)
        except ExistedService.DoesNotExist:
            return Response({'error': 'Service not found.'}, status=404)

        works = service.previous_works.select_related('completion_form').all()
        return Response(PreviousWorkSerializer(works, many=True).data)

class ProviderPreviousWorkView(APIView):
    permission_classes = [IsProviderOrAdmin]

    def get_form_or_work(self, request, booking_id, need='form'):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                form = ServiceCompletionForm.objects.get(booking__id=booking_id)
            else:
                form = ServiceCompletionForm.objects.get(
                    booking__id=booking_id,
                    booking__provider=request.user
                )
            if need == 'work':
                return form.previous_work
            return form
        except (ServiceCompletionForm.DoesNotExist, PreviousWork.DoesNotExist):
            return None

    def get(self, request, booking_id):
        work = self.get_form_or_work(request, booking_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)
        return Response(PreviousWorkSerializer(work).data)

    def post(self, request, booking_id):
        form = self.get_form_or_work(request, booking_id, need='form')
        if not form:
            return Response({'error': 'Completion form not found.'}, status=404)
        data = {}
        if 'before_image' in request.FILES:
            data['before_image'] = upload_image(request.FILES['before_image'], folder="previous_works")
        elif 'before_image' in request.data:
            data['before_image'] = request.data['before_image']  # URL مباشرة

        if 'after_image' in request.FILES:
            data['after_image'] = upload_image(request.FILES['after_image'], folder="previous_works")
        elif 'after_image' in request.data:
            data['after_image'] = request.data['after_image']
        serializer = PreviousWorkWriteSerializer(data=data, context={'form': form})
        serializer.is_valid(raise_exception=True)
        work = serializer.save()
        return Response(PreviousWorkSerializer(work).data, status=201)

    def patch(self, request, booking_id):
        work = self.get_form_or_work(request, booking_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)
        data = {}
        if 'before_image' in request.FILES:
            data['before_image'] = upload_image(request.FILES['before_image'], folder="previous_works")
        elif 'before_image' in request.data:
            data['before_image'] = request.data['before_image']  # URL مباشرة

        if 'after_image' in request.FILES:
            data['after_image'] = upload_image(request.FILES['after_image'], folder="previous_works")
        elif 'after_image' in request.data:
            data['after_image'] = request.data['after_image']
        for field, value in data.items():
            setattr(work, field, value)
        work.save()
        return Response(PreviousWorkSerializer(work).data)

    def delete(self, request, booking_id):
        work = self.get_form_or_work(request, booking_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)
        work.delete()
        return Response({'message': 'Previous work deleted successfully.'})
    

from accounts.permissions import IsProvider

class ProviderBookingListView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        status_filter = request.query_params.get('status')
        bookings = Booking.objects.filter(provider=request.user).select_related(
            'customer', 'service'
        ).prefetch_related('items__attribute')

        if status_filter in ('pending', 'confirmed', 'completed', 'cancelled'):
            bookings = bookings.filter(status=status_filter)

        return Response(BookingAdminSerializer(bookings, many=True).data)


class ProviderBookingDetailView(APIView):
    permission_classes = [IsProvider]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.select_related(
                'customer', 'service'
            ).prefetch_related('items__attribute').get(
                id=booking_id, provider=request.user
            )
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=404)
        return Response(BookingAdminSerializer(booking).data)


class ProviderBookingStatusView(APIView):
    permission_classes = [IsProvider]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id, provider=request.user)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=404)

        serializer = BookingStatusUpdateSerializer(
            data=request.data, context={'booking': booking}
        )
        serializer.is_valid(raise_exception=True)
        booking.status = serializer.validated_data['status']
        booking.save(update_fields=['status'])
        return Response(BookingAdminSerializer(booking).data)
    

class ProviderCompletionFormListView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        is_finished_param = request.query_params.get('is_finished')

        forms = ServiceCompletionForm.objects.filter(
            booking__isnull=False,
            booking__provider=request.user,
        ).select_related(
            'booking__service',
            'booking__address',
            'booking__address__city',
            'booking__address__region',
        ).prefetch_related(
            'booking__items__attribute'
        ).order_by('-created_at')

        if is_finished_param == 'true':
            forms = forms.filter(is_finished=True)
        elif is_finished_param == 'false':
            forms = forms.filter(is_finished=False)

        return Response(
            ProviderCompletionFormListSerializer(forms, many=True).data,
            status=status.HTTP_200_OK
        )