from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from utils.cloudinary import upload_image, upload_video
from accounts.permissions import IsCustomer, IsProvider, IsProviderOrAdmin
from .models import (
    CustomRequest, ServiceOffer, RequestChat,Notification,
    PlatformSettings,DeviceToken,CustomRequestImage
)
from existedservices.views import _resolve_image_field  # أو تنقلها لملف utils مشترك
from existedservices.models import ServiceCompletionForm, CompletionMedia , Booking,PreviousWork
from .serializers import (
    CustomRequestCreateSerializer,OnboardingSlideAdminSerializer,
    CustomRequestUpdateSerializer,ConversationSerializer,
    CustomRequestListSerializer,
    CustomRequestDetailSerializer,
    CustomRequestProviderDetailSerializer,AppMessageAdminSerializer,
    CustomRequestAdminSerializer,
    CustomRequestStatusUpdateSerializer,
    ServiceOfferSerializer,
    ServiceOfferCreateSerializer,
    ServiceOfferAdminSerializer,
    RequestChatSerializer,
    RequestChatCreateSerializer,ProviderCustomCompletionFormListSerializer,
    PlatformSettingsSerializer,NotificationSerializer,DeviceTokenRegisterSerializer,ProviderMyOfferSerializer,ServiceOfferUpdateSerializer
)
from existedservices.serializers import (
    ServiceCompletionFormSerializer,
    ServiceCompletionFormUpdateSerializer,
    CompletionMediaWriteSerializer,
    CompletionMediaSerializer,
    BookingStatusUpdateSerializer,  # Added import
    BookingAdminSerializer ,PreviousWorkSerializer, PreviousWorkWriteSerializer
)
from payments.permissions import IsProviderNotBlocked
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .consumers import chat_group
from django.utils import timezone
# ==================== HELPER ====================
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
    
def _check_and_expire(custom_request):
    """Lazy expiry check — يُستدعى عند جلب أي طلب."""
    custom_request.check_and_expire()

def _broadcast_read_receipt(request_id, reader_type, message_ids):
    """بيبلغ الطرف اللي بعت الرسائل الأصلية إنها اتقرت — نفس نمط _send_to_group في signals.py"""
    if not message_ids:
        return
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        chat_group(request_id),
        {
            'type': 'chat.read',
            'payload': {
                'event': 'messages_read',
                'request_id': str(request_id),
                'read_by': reader_type,
                'message_ids': [str(mid) for mid in message_ids],
                'read_at': timezone.now().isoformat(),
            },
        }
    )

import base64
import uuid as uuid_lib
from django.core.files.base import ContentFile

def _resolve_uploaded_image(request, folder):
    """
    بيرجع Cloudinary URL لو فيه صورة مبعوتة (multipart أو base64)، وإلا None.
    - Multipart: request.FILES['image']
    - Base64: request.data['image'] = "data:image/png;base64,...." أو base64 خام
    """
    if 'image' in request.FILES:
        return upload_image(request.FILES['image'], folder=folder)

    image_field = request.data.get('image')
    if image_field and isinstance(image_field, str) and not image_field.startswith('http'):
        # لو جاي بصيغة data URI: data:image/jpeg;base64,xxxx
        if ';base64,' in image_field:
            header, image_field = image_field.split(';base64,', 1)
            ext = header.split('/')[-1] if '/' in header else 'jpg'
        else:
            ext = 'jpg'

        try:
            decoded = base64.b64decode(image_field)
        except (TypeError, ValueError, base64.binascii.Error):
            raise ValueError("صيغة الصورة (base64) غير صحيحة.")

        file = ContentFile(decoded, name=f"{uuid_lib.uuid4()}.{ext}")
        return upload_image(file, folder=folder)

    return None

MAX_CUSTOM_REQUEST_IMAGES = 5

def _resolve_uploaded_images(request, folder):
    """
    بترجع list من Cloudinary URLs لكل الصور المبعوتة، سواء:
    - multipart: request.FILES.getlist('images')  ← نفس المفتاح لأكتر من ملف
    - base64: request.data['images'] كـ list من strings
    """
    urls = []

    # multipart
    for f in request.FILES.getlist('images'):
        urls.append(upload_image(f, folder=folder))

    # base64
    images_field = (
        request.data.getlist('images')
        if hasattr(request.data, 'getlist') else request.data.get('images')
    )
    if images_field:
        if isinstance(images_field, str):
            images_field = [images_field]
        for item in images_field:
            if not isinstance(item, str) or item.startswith('http'):
                continue
            if ';base64,' in item:
                header, raw = item.split(';base64,', 1)
                ext = header.split('/')[-1] if '/' in header else 'jpg'
            else:
                raw, ext = item, 'jpg'
            try:
                decoded = base64.b64decode(raw)
            except (TypeError, ValueError, base64.binascii.Error):
                raise ValueError("صيغة إحدى الصور (base64) غير صحيحة.")
            file = ContentFile(decoded, name=f"{uuid_lib.uuid4()}.{ext}")
            urls.append(upload_image(file, folder=folder))

    return urls


class CustomerCustomRequestListView(APIView):
    """
    GET  /custom-requests/          ← طلبات العميل
    POST /custom-requests/          ← ينشر طلب جديد
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        status_filter = request.query_params.get('status')
        date_from     = request.query_params.get('date_from')  # YYYY-MM-DD
        date_to       = request.query_params.get('date_to')    # YYYY-MM-DD

        requests = CustomRequest.objects.filter(
            customer=request.user
        ).select_related('specialization', 'address')

        if status_filter:
            requests = requests.filter(status=status_filter)

        if date_from:
            try:
                requests = requests.filter(scheduled_date__gte=date_from)
            except (ValueError, ValidationError):
                return Response(
                    {'error': 'صيغة date_from غير صحيحة. استخدم YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if date_to:
            try:
                requests = requests.filter(scheduled_date__lte=date_to)
            except (ValueError, ValidationError):
                return Response(
                    {'error': 'صيغة date_to غير صحيحة. استخدم YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Lazy expiry على القائمة
        for req in requests:
            _check_and_expire(req)

        # إعادة الجلب بعد التحديث المحتمل (بنفس الفلاتر)
        requests = CustomRequest.objects.filter(
            customer=request.user
        ).select_related('specialization', 'address')

        if status_filter:
            requests = requests.filter(status=status_filter)
        if date_from:
            requests = requests.filter(scheduled_date__gte=date_from)
        if date_to:
            requests = requests.filter(scheduled_date__lte=date_to)

        return Response(
            CustomRequestListSerializer(requests, many=True).data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        data = request.data.copy()

        try:
            image_urls = _resolve_uploaded_images(request, folder="custom_requests")
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if len(image_urls) > MAX_CUSTOM_REQUEST_IMAGES:
            return Response(
                {'error': f'الحد الأقصى {MAX_CUSTOM_REQUEST_IMAGES} صور لكل طلب.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CustomRequestCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        custom_request = serializer.save()

        if image_urls:
            CustomRequestImage.objects.bulk_create([
                CustomRequestImage(request=custom_request, image=url) for url in image_urls
            ])

        return Response(
            CustomRequestDetailSerializer(custom_request).data,
            status=status.HTTP_201_CREATED
        )


class CustomerCustomRequestDetailView(APIView):
    """
    GET   /custom-requests/<id>/   ← تفاصيل طلب
    PATCH /custom-requests/<id>/   ← تعديل الطلب
    """
    permission_classes = [IsCustomer]

    def get_object(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, customer=request.user)
            _check_and_expire(obj)
            return obj
        except CustomRequest.DoesNotExist:
            return None

    def get(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            CustomRequestDetailSerializer(obj).data,
            status=status.HTTP_200_OK
        )
    def patch(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response({'error': 'الطلب غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if obj.status not in ('published', 'offers_received'):
            return Response(
                {'error': 'لا يمكن تعديل هذا الطلب في وضعه الحالي.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # حذف صور محددة — request.data['remove_image_ids'] = ["id1", "id2"]
        remove_ids = request.data.get('remove_image_ids')
        if remove_ids:
            if isinstance(remove_ids, str):
                remove_ids = [remove_ids]
            obj.images.filter(id__in=remove_ids).delete()

        try:
            new_image_urls = _resolve_uploaded_images(request, folder="custom_requests")
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if obj.images.count() + len(new_image_urls) > MAX_CUSTOM_REQUEST_IMAGES:
            return Response(
                {'error': f'الحد الأقصى {MAX_CUSTOM_REQUEST_IMAGES} صور لكل طلب.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_image_urls:
            CustomRequestImage.objects.bulk_create([
                CustomRequestImage(request=obj, image=url) for url in new_image_urls
            ])

        serializer = CustomRequestUpdateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(CustomRequestDetailSerializer(obj).data, status=status.HTTP_200_OK)

class CustomerCancelRequestView(APIView):
    """
    POST /custom-requests/<id>/cancel/
    """
    permission_classes = [IsCustomer]

    def post(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, customer=request.user)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if obj.status in ('completed', 'cancelled', 'expired'):
            return Response(
                {'error': 'لا يمكن إلغاء هذا الطلب.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # إلغاء العروض المعلقة تلقائياً
        obj.offers.filter(status='pending').update(status='rejected')

        obj.status = 'cancelled'
        obj.save(update_fields=['status'])

        return Response(
            CustomRequestDetailSerializer(obj).data,
            status=status.HTTP_200_OK
        )


# ==================== CUSTOMER - OFFERS ====================

class CustomerOfferListView(APIView):
    """
    GET /custom-requests/<id>/offers/   ← العميل يشوف العروض
    """
    permission_classes = [IsCustomer]

    def get(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, customer=request.user)
            _check_and_expire(obj)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        offers = obj.offers.filter(status='pending').select_related('provider')
        return Response(
            ServiceOfferSerializer(offers, many=True).data,
            status=status.HTTP_200_OK
        )


class CustomerAcceptOfferView(APIView):
    """
    POST /custom-requests/<request_id>/offers/<offer_id>/accept/
    """
    permission_classes = [IsCustomer]

    def post(self, request, request_id, offer_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, customer=request.user)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if obj.status != 'offers_received':
            return Response(
                {'error': 'لا يمكن قبول عرض في هذه المرحلة.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            offer = obj.offers.get(id=offer_id, status='pending')
        except ServiceOffer.DoesNotExist:
            return Response(
                {'error': 'العرض غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # قبول العرض المختار
        offer.status = 'accepted'
        offer.save(update_fields=['status'])

        # رفض باقي العروض
        obj.offers.exclude(id=offer_id).filter(status='pending').update(status='rejected')

        # تحديث الطلب
        obj.status = 'accepted'
        obj.accepted_provider = offer.provider
        obj.save(update_fields=['status', 'accepted_provider'])

        # إنشاء نموذج الإتمام تلقائياً
        ServiceCompletionForm.objects.get_or_create(
            custom_request=obj,
            defaults={'booking': None}
        )

        return Response(
            CustomRequestDetailSerializer(obj).data,
            status=status.HTTP_200_OK
        )


# ==================== CUSTOMER - CHAT ====================

class CustomerChatView(APIView):
    """
    GET  /custom-requests/<id>/chat/?limit=30&offset=0
    POST /custom-requests/<id>/chat/
    """
    permission_classes = [IsCustomer]
 
    DEFAULT_LIMIT = 30
    MAX_LIMIT = 100
 
    def get_object(self, request, request_id):
        try:
            return CustomRequest.objects.get(id=request_id, customer=request.user)
        except CustomRequest.DoesNotExist:
            return None
 
    def get(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        messages_qs = obj.chat_messages.all()
        total_count = messages_qs.count()
 
        try:
            limit = int(request.query_params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))
 
        try:
            offset = int(request.query_params.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)
 
        # آخر رسائل أولاً منطقيًا للفرونت (زي واتساب: يفتح على آخر حاجة)
        # ordering الموديل الأصلي هو created_at تصاعدي، فبنعكس هنا للصفحة الأولى
        # ثم نرجعها لترتيبها الطبيعي عشان تتعرض تصاعديًا في الشاشة
        page = list(messages_qs.order_by('-created_at')[offset:offset + limit])
        page.reverse()
 
        return Response(
            {
                'count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count,
                'results': RequestChatSerializer(page, many=True).data,
            },
            status=status.HTTP_200_OK
        )
 
    def post(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        serializer = RequestChatCreateSerializer(
            data=request.data,
            context={
                'request': request,
                'custom_request': obj,
                'user_type': 'customer'
            }
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(
            RequestChatSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
 


 
class CustomerChatMarkReadView(APIView):
    """
    POST /custom-requests/<id>/chat/read/
    العميل بيعلّم كل رسائل الفني (اللي لسه مقروءة) كمقروءة، وبيتبعت
    إشعار لحظي للفني إن رسايله اتقرت (✓✓).
    """
    permission_classes = [IsCustomer]
 
    def post(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, customer=request.user)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        message_ids = RequestChat.mark_as_read_for_recipient(obj, recipient_type='customer')
        _broadcast_read_receipt(obj.id, reader_type='customer', message_ids=message_ids)
 
        return Response(
            {'marked_read_count': len(message_ids)},
            status=status.HTTP_200_OK
        )
 
# ==================== PROVIDER VIEWS ====================


from .utils.geo import get_provider_default_address, haversine_km
from .constants import DEFAULT_SERVICE_RADIUS_KM
class ProviderCustomRequestListView(APIView):
    """
    GET /provider/custom-requests/
    الفني يشوف الطلبات القريبة منه جغرافيًا (نفس التخصص + في نطاق X كم
    من عنوانه الافتراضي)، بدل الاعتماد على city/region اللي مش موجودين
    في موديل Provider أصلاً.
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]

    def get(self, request):
        provider = request.user

        provider_address = get_provider_default_address(provider)
        if not provider_address:
            return Response(
                {'error': 'يجب إضافة عنوان افتراضي بإحداثيات (lat/lng) أولاً.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        candidates = CustomRequest.objects.filter(
            status__in=('published', 'offers_received'),
            specialization=provider.specialization,
            address__lat__isnull=False,
            address__lng__isnull=False,
        ).select_related('specialization', 'address')

        # Lazy expiry أول حاجة
        for req in candidates:
            req.check_and_expire()

        # إعادة الجلب بعد التحديث المحتمل
        candidates = CustomRequest.objects.filter(
            status__in=('published', 'offers_received'),
            specialization=provider.specialization,
            address__lat__isnull=False,
            address__lng__isnull=False,
        ).select_related('specialization', 'address').prefetch_related('offers')

        # فلترة بالمسافة (مينفعش تتعمل في queryset filter عادي، بنعملها في بايثون)
        nearby_requests = [
            req for req in candidates
            if haversine_km(
                provider_address.lat, provider_address.lng,
                req.address.lat, req.address.lng
            ) <= DEFAULT_SERVICE_RADIUS_KM
        ]

        return Response(
            CustomRequestListSerializer(nearby_requests, many=True).data,
            status=status.HTTP_200_OK
        )


class ProviderCustomRequestDetailView(APIView):
    """
    GET /provider/custom-requests/<id>/
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]

    def get(self, request, request_id):
        provider = request.user

        provider_address = get_provider_default_address(provider)
        if not provider_address:
            return Response(
                {'error': 'يجب إضافة عنوان افتراضي بإحداثيات (lat/lng) أولاً.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            obj = CustomRequest.objects.select_related('specialization', 'address').get(
                id=request_id,
                specialization=provider.specialization,
            )
            _check_and_expire(obj)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود أو خارج نطاق منطقتك.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not obj.address or obj.address.lat is None or obj.address.lng is None:
            return Response(
                {'error': 'الطلب غير موجود أو خارج نطاق منطقتك.'},
                status=status.HTTP_404_NOT_FOUND
            )

        distance = haversine_km(
            provider_address.lat, provider_address.lng,
            obj.address.lat, obj.address.lng
        )
        if distance > DEFAULT_SERVICE_RADIUS_KM:
            return Response(
                {'error': 'الطلب غير موجود أو خارج نطاق منطقتك.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            CustomRequestProviderDetailSerializer(
                obj, context={'request': request}
            ).data,
            status=status.HTTP_200_OK
        )
# ==================== PROVIDER - OFFERS ====================

class ProviderOfferCreateView(APIView):
    """
    POST /provider/custom-requests/<id>/offers/   ← الفني يبعت عرض
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]

    def post(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id)
            _check_and_expire(obj)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServiceOfferCreateSerializer(
            data=request.data,
            context={
                'request': request,
                'custom_request': obj
            }
        )
        serializer.is_valid(raise_exception=True)
        offer = serializer.save()
        return Response(
            ServiceOfferSerializer(offer).data,
            status=status.HTTP_201_CREATED
        )

# ==================== PROVIDER - CHAT ====================
 
class ProviderChatView(APIView):
    """
    GET  /provider/custom-requests/<id>/chat/?limit=30&offset=0
    POST /provider/custom-requests/<id>/chat/
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]
 
    DEFAULT_LIMIT = 30
    MAX_LIMIT = 100
 
    def get_object(self, request, request_id):
        try:
            return CustomRequest.objects.get(
                id=request_id,
                accepted_provider=request.user
            )
        except CustomRequest.DoesNotExist:
            return None
 
    def get(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود أو غير مصرح لك.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        messages_qs = obj.chat_messages.all()
        total_count = messages_qs.count()
 
        try:
            limit = int(request.query_params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))
 
        try:
            offset = int(request.query_params.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)
 
        page = list(messages_qs.order_by('-created_at')[offset:offset + limit])
        page.reverse()
 
        return Response(
            {
                'count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count,
                'results': RequestChatSerializer(page, many=True).data,
            },
            status=status.HTTP_200_OK
        )
 
    def post(self, request, request_id):
        obj = self.get_object(request, request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود أو غير مصرح لك.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        serializer = RequestChatCreateSerializer(
            data=request.data,
            context={
                'request': request,
                'custom_request': obj,
                'user_type': 'provider'
            }
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(
            RequestChatSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
 
 
class ProviderChatMarkReadView(APIView):
    """
    POST /provider/custom-requests/<id>/chat/read/
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]
 
    def post(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id, accepted_provider=request.user)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود أو غير مصرح لك.'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        message_ids = RequestChat.mark_as_read_for_recipient(obj, recipient_type='provider')
        _broadcast_read_receipt(obj.id, reader_type='provider', message_ids=message_ids)
 
        return Response(
            {'marked_read_count': len(message_ids)},
            status=status.HTTP_200_OK
        )
# ==================== PROVIDER - COMPLETION FORM ====================

class ProviderCustomCompletionFormView(APIView):
    """
    GET   /provider/custom-requests/<id>/completion/
    PATCH /provider/custom-requests/<id>/completion/
    """
    permission_classes = [IsProviderOrAdmin]

    def get_form(self, request, request_id):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                return ServiceCompletionForm.objects.select_related(
                    'payment_request'
                ).get(
                    custom_request__id=request_id
                )
            else:
                return ServiceCompletionForm.objects.select_related(
                    'payment_request'
                ).get(
                    custom_request__id=request_id,
                    custom_request__accepted_provider=request.user
                )
        except ServiceCompletionForm.DoesNotExist:
            return None

    def get(self, request, request_id):
        form = self.get_form(request, request_id)
        if not form:
            return Response(
                {'error': 'نموذج الإتمام غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            ServiceCompletionFormSerializer(form).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, request_id):
        form = self.get_form(request, request_id)
        if not form:
            return Response(
                {'error': 'نموذج الإتمام غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServiceCompletionFormUpdateSerializer(
            form, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated_form = serializer.save()

        # لو الفني علّم الخدمة كـ finished، حدّث ستاتوس الطلب
        if updated_form.is_finished:
            custom_request = form.custom_request
            if custom_request and custom_request.status == 'in_progress':
                custom_request.status = 'completed'
                custom_request.save(update_fields=['status'])

        return Response(
            ServiceCompletionFormSerializer(updated_form).data,
            status=status.HTTP_200_OK
        )


class ProviderCustomCompletionMediaView(APIView):
    """
    POST   /provider/custom-requests/<id>/completion/media/
    DELETE /provider/custom-requests/<id>/completion/media/<media_id>/
    """
    permission_classes = [IsProviderOrAdmin]

    def get_form(self, request, request_id):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                return ServiceCompletionForm.objects.get(
                    custom_request__id=request_id
                )
            else:
                return ServiceCompletionForm.objects.get(
                    custom_request__id=request_id,
                    custom_request__accepted_provider=request.user
                )
        except ServiceCompletionForm.DoesNotExist:
            return None

    def post(self, request, request_id):
        form = self.get_form(request, request_id)
        if not form:
            return Response({'error': 'نموذج الإتمام غير موجود.'}, status=status.HTTP_404_NOT_FOUND)
        if form.is_finished:
            return Response({'error': 'لا يمكن إضافة وسائط لنموذج مكتمل.'}, status=status.HTTP_400_BAD_REQUEST)

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

    def delete(self, request, request_id, media_id):
        form = self.get_form(request, request_id)
        if not form:
            return Response(
                {'error': 'نموذج الإتمام غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if form.is_finished:
            return Response(
                {'error': 'لا يمكن حذف وسائط من نموذج مكتمل.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            media = CompletionMedia.objects.get(id=media_id, form=form)
        except CompletionMedia.DoesNotExist:
            return Response(
                {'error': 'الوسيطة غير موجودة.'},
                status=status.HTTP_404_NOT_FOUND
            )
        media.delete()
        return Response(
            {'message': 'تم الحذف بنجاح.'},
            status=status.HTTP_200_OK
        )


# ==================== ADMIN VIEWS ====================

class AdminCustomRequestListView(APIView):
    """
    GET /admin/custom-requests/   ← كل الطلبات مع فلترة
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter   = request.query_params.get('status')
        customer_filter = request.query_params.get('customer_id')
        city_filter     = request.query_params.get('city')
        region_filter   = request.query_params.get('region')

        requests_qs = CustomRequest.objects.select_related(
            'customer', 'specialization', 'address', 'accepted_provider'
        ).prefetch_related('offers')

        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
        if customer_filter:
            requests_qs = requests_qs.filter(customer_id=customer_filter)
        if city_filter:
            requests_qs = requests_qs.filter(address__city=city_filter)
        if region_filter:
            requests_qs = requests_qs.filter(address__region=region_filter)

        return Response(
            CustomRequestAdminSerializer(requests_qs, many=True).data,
            status=status.HTTP_200_OK
        )


class AdminCustomRequestDetailView(APIView):
    """
    GET /admin/custom-requests/<id>/
    """
    permission_classes = [IsAdminUser]

    def get_object(self, request_id):
        try:
            return CustomRequest.objects.select_related(
                'customer', 'specialization', 'address', 'accepted_provider'
            ).prefetch_related('offers__provider').get(id=request_id)
        except CustomRequest.DoesNotExist:
            return None

    def get(self, request, request_id):
        obj = self.get_object(request_id)
        if not obj:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            CustomRequestAdminSerializer(obj).data,
            status=status.HTTP_200_OK
        )


class AdminCustomRequestStatusView(APIView):
    """
    PATCH /admin/custom-requests/<id>/status/
    """
    permission_classes = [IsAdminUser]

    def patch(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CustomRequestStatusUpdateSerializer(
            data=request.data,
            context={'custom_request': obj}
        )
        serializer.is_valid(raise_exception=True)

        obj.status = serializer.validated_data['status']
        obj.save(update_fields=['status'])

        return Response(
            CustomRequestAdminSerializer(obj).data,
            status=status.HTTP_200_OK
        )


class AdminExpiredRequestsView(APIView):
    """
    GET /admin/custom-requests/expired/   ← الطلبات المنتهية للتدخل
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        expired_requests = CustomRequest.objects.filter(
            status='expired'
        ).select_related('customer', 'specialization', 'address').order_by('-expires_at')

        return Response(
            CustomRequestAdminSerializer(expired_requests, many=True).data,
            status=status.HTTP_200_OK
        )


class AdminCustomRequestOffersView(APIView):
    """
    GET /admin/custom-requests/<id>/offers/   ← كل العروض (للأدمن)
    """
    permission_classes = [IsAdminUser]

    def get(self, request, request_id):
        try:
            obj = CustomRequest.objects.get(id=request_id)
        except CustomRequest.DoesNotExist:
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        offers = obj.offers.select_related('provider').all()
        return Response(
            ServiceOfferAdminSerializer(offers, many=True).data,
            status=status.HTTP_200_OK
        )


# ==================== ADMIN - PLATFORM SETTINGS ====================

class AdminPlatformSettingsView(APIView):
    """
    GET   /admin/platform-settings/   ← يشوف الإعدادات
    PATCH /admin/platform-settings/   ← يعدل النسبة
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        settings_qs = PlatformSettings.objects.all()
        return Response(
            PlatformSettingsSerializer(settings_qs, many=True).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        key   = request.data.get('key')
        value = request.data.get('value')

        if not key or value is None:
            return Response(
                {'error': 'key و value مطلوبان.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        setting, _ = PlatformSettings.objects.get_or_create(key=key)
        serializer = PlatformSettingsSerializer(
            setting, data={'value': value}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            PlatformSettingsSerializer(setting).data,
            status=status.HTTP_200_OK
        )
    
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
    
class NotificationListView(APIView):
    """
    GET /notifications/?is_read=false&limit=20&offset=0

    limit  : عدد العناصر في الصفحة (افتراضي 20، أقصى حد 100)
    offset : من فين تبدأ (افتراضي 0)
    """
    permission_classes = [IsAuthenticated]

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def get(self, request):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type not in ('customer', 'provider'):
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        notifications = Notification.objects.filter(
            recipient_type=user_type,
            recipient_id=str(request.user.id),
        )

        is_read_param = request.query_params.get('is_read')
        if is_read_param == 'true':
            notifications = notifications.filter(is_read=True)
        elif is_read_param == 'false':
            notifications = notifications.filter(is_read=False)

        total_count = notifications.count()

        # limit/offset مع حماية من قيم غلط أو كبيرة أوي
        try:
            limit = int(request.query_params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))

        try:
            offset = int(request.query_params.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)

        page = notifications[offset:offset + limit]

        return Response(
            {
                'count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count,
                'results': NotificationSerializer(page, many=True).data,
            },
            status=status.HTTP_200_OK
        )
    

class NotificationUnreadCountView(APIView):
    """
    GET /notifications/unread-count/   ← لعمل الـ badge على أيقونة الجرس
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type not in ('customer', 'provider'):
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)
 
        count = Notification.objects.filter(
            recipient_type=user_type,
            recipient_id=str(request.user.id),
            is_read=False,
        ).count()
 
        return Response({'unread_count': count}, status=status.HTTP_200_OK)
 
 
class NotificationMarkReadView(APIView):
    """
    PATCH /notifications/<notification_id>/read/
    """
    permission_classes = [IsAuthenticated]
 
    def patch(self, request, notification_id):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient_type=user_type,
                recipient_id=str(request.user.id),
            )
        except Notification.DoesNotExist:
            return Response({'error': 'الإشعار غير موجود.'}, status=status.HTTP_404_NOT_FOUND)
 
        notification.mark_as_read()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)
 
 
class NotificationMarkAllReadView(APIView):
    """
    POST /notifications/mark-all-read/
    """
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type not in ('customer', 'provider'):
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)
 
        Notification.objects.filter(
            recipient_type=user_type,
            recipient_id=str(request.user.id),
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
 
        return Response({'message': 'تم تعليم الكل كمقروء.'}, status=status.HTTP_200_OK)
    


class DeviceTokenView(APIView):
    """
    POST   /device-tokens/   body: {"token": "<fcm_token>"}
        بتتنادى:
        - وقت تسجيل الدخول (بعد الحصول على FCM token من Firebase SDK)
        - أي مرة يحصل فيها onTokenRefresh في التطبيق (Firebase بيغيّر
          التوكن من وقت للتاني تلقائيًا، مش بس أول مرة)
 
    DELETE /device-tokens/   body: {"token": "<fcm_token>"}
        بتتنادى وقت تسجيل الخروج (logout) — عشان مبعتش إشعارات ليوزر
        مسجل خروج على جهاز مش بتاعه دلوقتي.
    """
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type not in ('customer', 'provider'):
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)
 
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
 
        # لو التوكن ده كان مسجل قبل كده على يوزر تاني (نادر بس ممكن، مثلاً
        # جهاز اتباع من يوزر ليوزر تاني)، ننقله لليوزر الحالي بدل ما نعمل duplicate error
        DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'recipient_type': user_type,
                'recipient_id': str(request.user.id),
            }
        )
 
        return Response({'message': 'تم تسجيل التوكن بنجاح.'}, status=status.HTTP_200_OK)
 
    def delete(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'token مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)
 
        DeviceToken.objects.filter(token=token).delete()
        return Response({'message': 'تم حذف التوكن.'}, status=status.HTTP_200_OK)
 


class ProviderMyOffersListView(APIView):
    """
    GET /provider/offers/?status=pending
    الفني يشوف كل العروض اللي بعتها هو، بحالتها (accepted/rejected/pending/withdrawn)
    """
    permission_classes = [IsProvider, IsProviderNotBlocked]


    def get(self, request):
        status_filter = request.query_params.get('status')

        offers = ServiceOffer.objects.filter(
            provider=request.user
        ).select_related(
            'request', 'request__specialization', 'request__address'
        ).order_by('-created_at')

        if status_filter in ('pending', 'accepted', 'rejected', 'withdrawn'):
            offers = offers.filter(status=status_filter)

        return Response(
            ProviderMyOfferSerializer(offers, many=True).data,
            status=status.HTTP_200_OK
        )
    
class ProviderOfferWithdrawView(APIView):
    """
    GET    /provider/offers/<offer_id>/   ← الفني يشوف تفاصيل عرضه
    PATCH  /provider/offers/<offer_id>/   ← الفني يعدل عرضه (لو لسه pending)
    DELETE /provider/offers/<offer_id>/   ← الفني يسحب عرضه
    """
    permission_classes = [IsProvider]

    def get_object(self, request, offer_id):
        try:
            return ServiceOffer.objects.select_related(
                'request', 'request__specialization', 'request__address'
            ).get(id=offer_id, provider=request.user)
        except ServiceOffer.DoesNotExist:
            return None

    def get(self, request, offer_id):
        offer = self.get_object(request, offer_id)
        if not offer:
            return Response(
                {'error': 'العرض غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            ProviderMyOfferSerializer(offer).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, offer_id):
        offer = self.get_object(request, offer_id)
        if not offer:
            return Response(
                {'error': 'العرض غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServiceOfferUpdateSerializer(
            data=request.data,
            context={'offer': offer}
        )
        serializer.is_valid(raise_exception=True)
        updated_offer = serializer.update(offer, serializer.validated_data)
        return Response(
            ProviderMyOfferSerializer(updated_offer).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, offer_id):
        try:
            offer = ServiceOffer.objects.get(
                id=offer_id,
                provider=request.user,
                status='pending'
            )
        except ServiceOffer.DoesNotExist:
            return Response(
                {'error': 'العرض غير موجود أو لا يمكن سحبه.'},
                status=status.HTTP_404_NOT_FOUND
            )

        offer.status = 'withdrawn'
        offer.save(update_fields=['status'])

        custom_request = offer.request
        if not custom_request.offers.filter(status='pending').exists():
            if custom_request.status == 'offers_received':
                custom_request.status = 'published'
                custom_request.save(update_fields=['status'])

        return Response(
            {'message': 'تم سحب العرض بنجاح.'},
            status=status.HTTP_200_OK
        )
    
class CustomerConfirmProviderArrivalCustomRequestView(APIView):
    """
    POST /custom-requests/<request_id>/provider-arrived/
    العميل يأكد إن الفني وصل → status النموذج يتحول لـ provider_arrived
    و started_at بياخد وقت وتاريخ اللحظة دي.
    """
    permission_classes = [IsCustomer]

    def post(self, request, request_id):
        try:
            form = ServiceCompletionForm.objects.select_related('payment_request').get(
                custom_request__id=request_id,
                custom_request__customer=request.user
            )
        except ServiceCompletionForm.DoesNotExist:
            return Response({'error': 'نموذج الإتمام غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if form.status == 'provider_arrived':
            return Response({'error': 'تم تأكيد وصول الفني بالفعل.'}, status=status.HTTP_400_BAD_REQUEST)

        form.status     = 'provider_arrived'
        form.started_at = timezone.now()
        form.save(update_fields=['status', 'started_at'])

        # ← الإضافة: حرّك CustomRequest نفسه لـ in_progress دلوقتي،
        # عشان لما الفني يعمل finish بعدين، الشرط في ProviderCustomCompletionFormView
        # يتحقق فعليًا ويحوّل الطلب لـ completed
        custom_request = form.custom_request
        if custom_request and custom_request.status == 'accepted':
            custom_request.status = 'in_progress'
            custom_request.save(update_fields=['status'])

        return Response(
            ServiceCompletionFormSerializer(form).data,
            status=status.HTTP_200_OK
        )
    

class ProviderCustomPreviousWorkView(APIView):
    permission_classes = [IsProviderOrAdmin]

    def get_form_or_work(self, request, request_id, need='form'):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        try:
            if user_type == 'admin':
                form = ServiceCompletionForm.objects.get(custom_request__id=request_id)
            else:
                form = ServiceCompletionForm.objects.get(
                    custom_request__id=request_id,
                    custom_request__accepted_provider=request.user
                )
            if need == 'work':
                return form.previous_work
            return form
        except (ServiceCompletionForm.DoesNotExist, PreviousWork.DoesNotExist):
            return None

    def get(self, request, request_id):
        work = self.get_form_or_work(request, request_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)
        return Response(PreviousWorkSerializer(work).data)

    def post(self, request, request_id):
        form = self.get_form_or_work(request, request_id, need='form')
        if not form:
            return Response({'error': 'Completion form not found.'}, status=404)

        if form.status != 'provider_arrived':
            return Response(
                {'error': 'لا يمكن رفع before_image قبل تأكيد العميل وصول الفني.'},
                status=400
            )

        if 'after_image' in request.data or 'after_image' in request.FILES:
            return Response(
                {'error': 'لا يمكن رفع after_image عند بدء الشغل. استخدم PATCH بعد إنهاء الشغل.'},
                status=400
            )

        try:
            before_url = _resolve_image_field(request, 'before_image', folder="previous_works")
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        if not before_url:
            return Response({'error': 'before_image is required.'}, status=400)

        serializer = PreviousWorkWriteSerializer(
            data={'before_image': before_url},
            context={'form': form}
        )
        serializer.is_valid(raise_exception=True)
        work = serializer.save()
        return Response(PreviousWorkSerializer(work).data, status=201)

    def patch(self, request, request_id):
        work = self.get_form_or_work(request, request_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)

        try:
            before_url = _resolve_image_field(request, 'before_image', folder="previous_works")
            after_url  = _resolve_image_field(request, 'after_image', folder="previous_works")
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        data = {}
        if before_url:
            data['before_image'] = before_url
        if after_url:
            data['after_image'] = after_url

        for field, value in data.items():
            setattr(work, field, value)
        work.save()
        return Response(PreviousWorkSerializer(work).data)

    def delete(self, request, request_id):
        work = self.get_form_or_work(request, request_id, need='work')
        if not work:
            return Response({'error': 'Previous work not found.'}, status=404)
        work.delete()
        return Response({'message': 'Previous work deleted successfully.'})
    

class ProviderCustomCompletionFormListView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        is_finished_param = request.query_params.get('is_finished')

        forms = ServiceCompletionForm.objects.filter(
            custom_request__isnull=False,
            custom_request__accepted_provider=request.user,
        ).select_related(
            'custom_request',
            'custom_request__specialization',
            'custom_request__address',
            'payment_request',  # ← جديد — يمنع query إضافي لكل عنصر في اللستة
        ).order_by('-created_at')

        if is_finished_param == 'true':
            forms = forms.filter(is_finished=True)
        elif is_finished_param == 'false':
            forms = forms.filter(is_finished=False)

        return Response(
            ProviderCustomCompletionFormListSerializer(forms, many=True).data,
            status=status.HTTP_200_OK
        )

class CustomerCustomCompletionFormView(APIView):
    """
    GET /custom-requests/<request_id>/completion/
    العميل يشوف تفاصيل نموذج الإتمام بتاع طلبه المخصص (بدون تعديل)
    """
    permission_classes = [IsCustomer]

    def get(self, request, request_id):
        try:
            form = ServiceCompletionForm.objects.select_related('payment_request').get(
                custom_request__id=request_id,
                custom_request__customer=request.user
            )
        except ServiceCompletionForm.DoesNotExist:
            return Response(
                {'error': 'نموذج الإتمام غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(ServiceCompletionFormSerializer(form).data)
    
from .models import OnboardingSlide
from .serializers import OnboardingSlideSerializer


class OnboardingListView(APIView):
    """
    GET /onboarding/
    بيرجع كل سلايدز الـ onboarding النشطة، مرتبة حسب order.
    عام (مش محتاج تسجيل دخول) عشان يتعرض أول ما التطبيق يفتح.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        slides = OnboardingSlide.objects.filter(is_active=True)
        return Response(
            OnboardingSlideSerializer(slides, many=True).data,
            status=status.HTTP_200_OK
        )
    

from django.utils import timezone
from .models import AppMessage
from .serializers import AppMessageSerializer


def _active_messages_qs(audience):
    now = timezone.now()
    return AppMessage.objects.filter(
        audience=audience,
        is_active=True,
    ).filter(
        models.Q(start_at__isnull=True) | models.Q(start_at__lte=now)
    ).filter(
        models.Q(end_at__isnull=True) | models.Q(end_at__gte=now)
    )


class CustomerAppMessageListView(APIView):
    """
    GET /customer/messages/
    الرسائل الموجهة للعميل فقط.
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        messages = _active_messages_qs('customer')
        return Response(
            AppMessageSerializer(messages, many=True).data,
            status=status.HTTP_200_OK
        )


class ProviderAppMessageListView(APIView):
    """
    GET /provider/messages/
    الرسائل الموجهة للفني فقط.
    """
    permission_classes = [IsProvider]

    def get(self, request):
        messages = _active_messages_qs('provider')
        return Response(
            AppMessageSerializer(messages, many=True).data,
            status=status.HTTP_200_OK
        )
    
class AdminAppMessageListView(APIView):
    """
    GET  /admin/messages/    ← كل الرسائل (مع فلترة اختيارية بـ audience)
    POST /admin/messages/    ← إنشاء رسالة جديدة
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        audience_filter = request.query_params.get('audience')

        messages = AppMessage.objects.all()
        if audience_filter in ('customer', 'provider'):
            messages = messages.filter(audience=audience_filter)

        return Response(
            AppMessageAdminSerializer(messages, many=True).data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = AppMessageAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(
            AppMessageAdminSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
    
class AdminAppMessageDetailView(APIView):
    """
    GET    /admin/messages/<id>/
    PATCH  /admin/messages/<id>/
    DELETE /admin/messages/<id>/
    """
    permission_classes = [IsAdminUser]

    def get_object(self, message_id):
        try:
            return AppMessage.objects.get(id=message_id)
        except AppMessage.DoesNotExist:
            return None

    def get(self, request, message_id):
        message = self.get_object(message_id)
        if not message:
            return Response({'error': 'الرسالة غير موجودة.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppMessageAdminSerializer(message).data, status=status.HTTP_200_OK)

    def patch(self, request, message_id):
        message = self.get_object(message_id)
        if not message:
            return Response({'error': 'الرسالة غير موجودة.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AppMessageAdminSerializer(message, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AppMessageAdminSerializer(message).data, status=status.HTTP_200_OK)

    def delete(self, request, message_id):
        message = self.get_object(message_id)
        if not message:
            return Response({'error': 'الرسالة غير موجودة.'}, status=status.HTTP_404_NOT_FOUND)

        message.delete()
        return Response({'message': 'تم الحذف بنجاح.'}, status=status.HTTP_200_OK)
    

class AdminOnboardingSlideListView(APIView):
    """
    GET  /admin/onboarding/    ← كل السلايدز (نشطة وغير نشطة)
    POST /admin/onboarding/    ← إضافة سلايد جديد
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        slides = OnboardingSlide.objects.all()
        return Response(
            OnboardingSlideAdminSerializer(slides, many=True).data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        data = request.data.copy()
        try:
            image_url = _resolve_uploaded_image(request, folder="onboarding")
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if image_url:
            data['image'] = image_url

        serializer = OnboardingSlideAdminSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        slide = serializer.save()
        return Response(
            OnboardingSlideAdminSerializer(slide).data,
            status=status.HTTP_201_CREATED
        )


class AdminOnboardingSlideDetailView(APIView):
    """
    GET    /admin/onboarding/<id>/
    PATCH  /admin/onboarding/<id>/
    DELETE /admin/onboarding/<id>/
    """
    permission_classes = [IsAdminUser]

    def get_object(self, slide_id):
        try:
            return OnboardingSlide.objects.get(id=slide_id)
        except OnboardingSlide.DoesNotExist:
            return None

    def get(self, request, slide_id):
        slide = self.get_object(slide_id)
        if not slide:
            return Response({'error': 'السلايد غير موجود.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OnboardingSlideAdminSerializer(slide).data, status=status.HTTP_200_OK)

    def patch(self, request, slide_id):
        slide = self.get_object(slide_id)
        if not slide:
            return Response({'error': 'السلايد غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        try:
            image_url = _resolve_uploaded_image(request, folder="onboarding")
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if image_url:
            data['image'] = image_url

        serializer = OnboardingSlideAdminSerializer(slide, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OnboardingSlideAdminSerializer(slide).data, status=status.HTTP_200_OK)

    def delete(self, request, slide_id):
        slide = self.get_object(slide_id)
        if not slide:
            return Response({'error': 'السلايد غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        slide.delete()
        return Response({'message': 'تم الحذف بنجاح.'}, status=status.HTTP_200_OK)
    

from django.db.models import Count, Q


class CustomerConversationsListView(APIView):
    """
    GET /custom-requests/conversations/?limit=20&offset=0

    بيرجع كل المحادثات (طلبات فيها فني مقبول وبدأ فيها شات) الخاصة
    بالعميل الحالي، مرتبة من الأحدث رسالة للأقدم.
    """
    permission_classes = [IsCustomer]

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def get(self, request):
        conversations_qs = CustomRequest.objects.filter(
            customer=request.user,
            accepted_provider__isnull=False,
        ).select_related(
            'accepted_provider', 'specialization'
        ).prefetch_related(
            'chat_messages'
        ).annotate(
            unread_count=Count(
                'chat_messages',
                filter=Q(chat_messages__sender_type='provider', chat_messages__is_read=False)
            )
        )

        conversations = []
        for obj in conversations_qs:
            # الرسائل متجابة أصلاً بالـ prefetch ومترتبة تصاعدياً (Meta.ordering)
            messages = list(obj.chat_messages.all())
            if not messages:
                continue  # مفيش شات اتبدأ لسه على الطلب ده، منعرضوش كمحادثة

            obj._last_message = messages[-1]
            conversations.append(obj)

        # ترتيب حسب وقت آخر رسالة، الأحدث أولاً
        conversations.sort(key=lambda c: c._last_message.created_at, reverse=True)

        # Pagination
        try:
            limit = int(request.query_params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))

        try:
            offset = int(request.query_params.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)

        total_count = len(conversations)
        page = conversations[offset:offset + limit]

        return Response({
            'count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count,
            'results': ConversationSerializer(page, many=True).data,
        }, status=status.HTTP_200_OK)