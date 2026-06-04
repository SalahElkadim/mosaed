from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser

from accounts.permissions import IsCustomer, IsProvider, IsProviderOrAdmin
from .models import (
    CustomRequest, ServiceOffer, RequestChat,
    PlatformSettings
)
from existedservices.models import ServiceCompletionForm, CompletionMedia
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
    PlatformSettingsSerializer,
)
from existedservices.serializers import (
    ServiceCompletionFormSerializer,
    ServiceCompletionFormUpdateSerializer,
    CompletionMediaWriteSerializer,
    CompletionMediaSerializer,
)


# ==================== HELPER ====================

def _check_and_expire(custom_request):
    """Lazy expiry check — يُستدعى عند جلب أي طلب."""
    custom_request.check_and_expire()


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
    GET  /custom-requests/<id>/chat/
    POST /custom-requests/<id>/chat/
    """
    permission_classes = [IsCustomer]

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

        messages = obj.chat_messages.all()
        return Response(
            RequestChatSerializer(messages, many=True).data,
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


# ==================== PROVIDER VIEWS ====================

class ProviderCustomRequestListView(APIView):
    """
    GET /provider/custom-requests/
    الفني يشوف الطلبات في منطقته (city + region + specialization)
    """
    permission_classes = [IsProvider]

    def get(self, request):
        provider = request.user

        # المطابقة على المنطقة والتخصص
        requests_qs = CustomRequest.objects.filter(
            status__in=('published', 'offers_received'),
            specialization=provider.specialization,
            address__city=provider.city,
            address__region=provider.region,
        ).select_related('specialization', 'address').prefetch_related('offers')

        # Lazy expiry
        ids_to_expire = []
        for req in requests_qs:
            if req.check_and_expire():
                ids_to_expire.append(req.id)

        # إعادة الجلب بعد التحديث
        requests_qs = CustomRequest.objects.filter(
            status__in=('published', 'offers_received'),
            specialization=provider.specialization,
            address__city=provider.city,
            address__region=provider.region,
        ).select_related('specialization', 'address')

        return Response(
            CustomRequestListSerializer(requests_qs, many=True).data,
            status=status.HTTP_200_OK
        )


class ProviderCustomRequestDetailView(APIView):
    """
    GET /provider/custom-requests/<id>/
    """
    permission_classes = [IsProvider]

    def get(self, request, request_id):
        provider = request.user
        try:
            obj = CustomRequest.objects.get(
                id=request_id,
                specialization=provider.specialization,
                address__city=provider.city,
                address__region=provider.region,
            )
            _check_and_expire(obj)
        except CustomRequest.DoesNotExist:
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
    GET  /provider/custom-requests/<id>/chat/
    POST /provider/custom-requests/<id>/chat/
    """
    permission_classes = [IsProvider]

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
        messages = obj.chat_messages.all()
        return Response(
            RequestChatSerializer(messages, many=True).data,
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

        serializer = CompletionMediaWriteSerializer(data=request.data)
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