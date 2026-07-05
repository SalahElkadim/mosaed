from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from utils.cloudinary import upload_image, upload_video
from accounts.permissions import IsCustomer, IsProvider, IsProviderOrAdmin
from .models import (
    CustomRequest, ServiceOffer, RequestChat,Notification,
    PlatformSettings,DeviceToken
)
from existedservices.models import ServiceCompletionForm, CompletionMedia , Booking
from .serializers import (
    CustomRequestCreateSerializer,
    CustomRequestUpdateSerializer,
    CustomRequestListSerializer,
    CustomRequestDetailSerializer,
    CustomRequestProviderDetailSerializer,
    CustomRequestAdminSerializer,
    CustomRequestStatusUpdateSerializer,
    ServiceOfferSerializer,
    ServiceOfferCreateSerializer,
    ServiceOfferAdminSerializer,
    RequestChatSerializer,
    RequestChatCreateSerializer,
    PlatformSettingsSerializer,NotificationSerializer,DeviceTokenRegisterSerializer
)
from existedservices.serializers import (
    ServiceCompletionFormSerializer,
    ServiceCompletionFormUpdateSerializer,
    CompletionMediaWriteSerializer,
    CompletionMediaSerializer,
    BookingStatusUpdateSerializer,  # Added import
    BookingAdminSerializer # Import added for fixing the issue
)

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .consumers import chat_group
from django.utils import timezone
# ==================== HELPER ====================

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
# ==================== CUSTOMER VIEWS ====================

class CustomerCustomRequestListView(APIView):
    """
    GET  /custom-requests/          ← طلبات العميل
    POST /custom-requests/          ← ينشر طلب جديد
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        status_filter = request.query_params.get('status')
        requests = CustomRequest.objects.filter(
            customer=request.user
        ).select_related('specialization', 'address')

        if status_filter:
            requests = requests.filter(status=status_filter)

        # Lazy expiry على القائمة
        for req in requests:
            _check_and_expire(req)

        # إعادة الجلب بعد التحديث المحتمل
        requests = CustomRequest.objects.filter(
            customer=request.user
        ).select_related('specialization', 'address')
        if status_filter:
            requests = requests.filter(status=status_filter)

        return Response(
            CustomRequestListSerializer(requests, many=True).data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = CustomRequestCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        custom_request = serializer.save()
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
            return Response(
                {'error': 'الطلب غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # التعديل مسموح فقط على الطلبات النشطة
        if obj.status not in ('published', 'offers_received'):
            return Response(
                {'error': 'لا يمكن تعديل هذا الطلب في وضعه الحالي.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CustomRequestUpdateSerializer(
            obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            CustomRequestDetailSerializer(obj).data,
            status=status.HTTP_200_OK
        )


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
    permission_classes = [IsProvider]

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
    permission_classes = [IsProvider]

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
    permission_classes = [IsProvider]

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


class ProviderOfferWithdrawView(APIView):
    """
    DELETE /provider/offers/<offer_id>/   ← الفني يسحب عرضه
    """
    permission_classes = [IsProvider]

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

        # لو مفيش عروض pending تانية، رجّع الطلب لـ published
        custom_request = offer.request
        if not custom_request.offers.filter(status='pending').exists():
            if custom_request.status == 'offers_received':
                custom_request.status = 'published'
                custom_request.save(update_fields=['status'])

        return Response(
            {'message': 'تم سحب العرض بنجاح.'},
            status=status.HTTP_200_OK
        )


# ==================== PROVIDER - CHAT ====================
 
class ProviderChatView(APIView):
    """
    GET  /provider/custom-requests/<id>/chat/?limit=30&offset=0
    POST /provider/custom-requests/<id>/chat/
    """
    permission_classes = [IsProvider]
 
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
    permission_classes = [IsProvider]
 
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
            return Response(
                {'error': 'نموذج الإتمام غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if form.is_finished:
            return Response(
                {'error': 'لا يمكن إضافة وسائط لنموذج مكتمل.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if 'media' not in request.FILES:
            return Response(
                {'error': 'media file is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        media_type = request.data.get('media_type')
        if media_type not in ('image', 'video'):
            return Response(
                {'error': 'media_type must be image or video.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if media_type == 'video':
            result = upload_video(request.FILES['media'], folder="completion_media")
            media_url     = result['url']
            thumbnail_url = result['thumbnail']
        else:
            media_url     = upload_image(request.FILES['media'], folder="completion_media")
            thumbnail_url = None

        data = request.data.copy()
        data['media_url']     = media_url
        data['thumbnail_url'] = thumbnail_url

        serializer = CompletionMediaWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        media = serializer.save(form=form)
        return Response(
            CompletionMediaSerializer(media).data,
            status=status.HTTP_201_CREATED
        )

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
 