from rest_framework import serializers
from django.utils import timezone

from accounts.models import CustomerAddress, Provider, Specialization
from accounts.serializers import CustomerAddressSerializer, SpecializationSerializer

from .models import CustomRequest, ServiceOffer, RequestChat, PlatformSettings,CustomRequestImage,OnboardingSlide


# ==================== PLATFORM SETTINGS ====================

class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlatformSettings
        fields = ['key', 'value', 'updated_at']
        read_only_fields = ['key', 'updated_at']




class CustomRequestImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomRequestImage
        fields = ['id', 'image', 'created_at']
        read_only_fields = fields
# ==================== CUSTOM REQUEST ====================

class CustomRequestCreateSerializer(serializers.Serializer):
    """العميل ينشر طلب جديد"""
    specialization_id = serializers.UUIDField()
    title             = serializers.CharField(max_length=255)
    description       = serializers.CharField()
    scheduled_date    = serializers.DateField()

    # العنوان — إما ID من عناوينه أو عنوان جديد
    address_id   = serializers.UUIDField(required=False)
    address_data = CustomerAddressSerializer(required=False)

    def validate_specialization_id(self, value):
        try:
            return Specialization.objects.get(id=value, is_active=True)
        except Specialization.DoesNotExist:
            raise serializers.ValidationError("التخصص غير موجود أو غير نشط.")

    def validate_scheduled_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("تاريخ الخدمة لا يمكن أن يكون في الماضي.")
        return value

    def validate(self, attrs):
        # لازم يبعت address_id أو address_data
        if not attrs.get('address_id') and not attrs.get('address_data'):
            raise serializers.ValidationError(
                "يجب تحديد عنوان الخدمة (address_id أو address_data)."
            )
        return attrs

    def create(self, validated_data):
        customer       = self.context['request'].user
        specialization = validated_data.pop('specialization_id')   # بعد الـ validate بقى Object
        address_id     = validated_data.pop('address_id', None)
        address_data   = validated_data.pop('address_data', None)

        if address_data:
            address = CustomerAddress.objects.create(customer=customer, **address_data)
        else:
            try:
                address = CustomerAddress.objects.get(id=address_id, customer=customer)
            except CustomerAddress.DoesNotExist:
                raise serializers.ValidationError("العنوان غير موجود.")

        return CustomRequest.objects.create(
            customer=customer,
            specialization=specialization,
            address=address,
            **validated_data
        )


class CustomRequestUpdateSerializer(serializers.ModelSerializer):
    """
    قبل أي عروض: تعديل حر
    بعد العروض:  description و image بس
    """
    class Meta:
        model  = CustomRequest
        fields = ['title', 'description', 'specialization', 'scheduled_date']

    def validate(self, attrs):
        request_obj = self.instance
        has_offers  = request_obj.offers.filter(
            status='pending'
        ).exists()

        # لو في عروض، امنع تغيير التخصص والموعد
        if has_offers:
            if 'specialization' in attrs:
                raise serializers.ValidationError(
                    "لا يمكن تغيير التخصص بعد وصول عروض."
                )
            if 'scheduled_date' in attrs:
                raise serializers.ValidationError(
                    "لا يمكن تغيير الموعد بعد وصول عروض."
                )
            if 'title' in attrs:
                raise serializers.ValidationError(
                    "لا يمكن تغيير العنوان بعد وصول عروض."
                )
        return attrs


class CustomRequestListSerializer(serializers.ModelSerializer):
    """قائمة خفيفة — للعميل والفني"""
    specialization_name = serializers.CharField(
        source='specialization.name', read_only=True
    )
    city    = serializers.CharField(source='address.city',    read_only=True)
    region  = serializers.CharField(source='address.region',  read_only=True)
    district = serializers.CharField(source='address.district', read_only=True)
    offers_count = serializers.IntegerField(
        source='offers.count', read_only=True
    )
    images = CustomRequestImageSerializer(many=True, read_only=True)
    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'specialization_name','images',
            'city', 'region', 'district',
            'scheduled_date', 'status', 'expires_at',
            'offers_count', 'created_at'
        ]
        read_only_fields = fields


class CustomRequestDetailSerializer(serializers.ModelSerializer):
    """تفاصيل كاملة — للعميل"""
    specialization = SpecializationSerializer(read_only=True)
    address        = CustomerAddressSerializer(read_only=True)
    offers_count   = serializers.IntegerField(source='offers.count', read_only=True)
    images = CustomRequestImageSerializer(many=True, read_only=True)
    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'description', 'images',
            'specialization', 'address',
            'scheduled_date', 'status', 'expires_at',
            'accepted_provider', 'offers_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class CustomRequestProviderDetailSerializer(serializers.ModelSerializer):
    """تفاصيل الطلب للفني — بدون عروض تانية"""
    specialization = SpecializationSerializer(read_only=True)
    city     = serializers.CharField(source='address.city',     read_only=True)
    region   = serializers.CharField(source='address.region',   read_only=True)
    district = serializers.CharField(source='address.district', read_only=True)

    # هل الفني ده عمل عرض قبل كده؟
    my_offer = serializers.SerializerMethodField()
    images = CustomRequestImageSerializer(many=True, read_only=True)
    def get_my_offer(self, obj):
        provider = self.context['request'].user
        offer    = obj.offers.filter(provider=provider).first()
        if offer:
            return ServiceOfferSerializer(offer).data
        return None

    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'description', 'images',
            'specialization', 'city', 'region', 'district',
            'scheduled_date', 'status', 'expires_at',
            'my_offer', 'created_at'
        ]
        read_only_fields = fields


class CustomRequestAdminSerializer(serializers.ModelSerializer):
    """للأدمن — كل التفاصيل"""
    specialization   = SpecializationSerializer(read_only=True)
    address          = CustomerAddressSerializer(read_only=True)
    customer_name    = serializers.CharField(source='customer.name',         read_only=True)
    customer_phone   = serializers.CharField(source='customer.phone_number', read_only=True)
    accepted_provider_name = serializers.CharField(
        source='accepted_provider.name', read_only=True
    )
    offers_count = serializers.IntegerField(source='offers.count', read_only=True)
    images = CustomRequestImageSerializer(many=True, read_only=True)
    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'customer_name', 'customer_phone',
            'title', 'description', 'images',
            'specialization', 'address',
            'scheduled_date', 'status', 'expires_at',
            'accepted_provider', 'accepted_provider_name',
            'offers_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


# ==================== SERVICE OFFER ====================

class ServiceOfferSerializer(serializers.ModelSerializer):
    """عرض واحد — للعميل يشوف العروض"""
    provider_name  = serializers.CharField(source='provider.name',         read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    average_rating = serializers.DecimalField(
        source='provider.average_rating',
        max_digits=3, decimal_places=2, read_only=True
    )
    total_reviews  = serializers.IntegerField(
        source='provider.total_reviews', read_only=True
    )

    class Meta:
        model  = ServiceOffer
        fields = [
            'id', 'provider_name', 'provider_phone',
            'average_rating', 'total_reviews',
            'final_price',    # العميل بيشوف السعر النهائي بس
            'note', 'status', 'created_at'
        ]
        read_only_fields = fields

from .utils.geo import get_provider_default_address, haversine_km
from .constants import DEFAULT_SERVICE_RADIUS_KM
class ServiceOfferCreateSerializer(serializers.Serializer):
    """الفني يبعت عرض"""
    provider_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    note           = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_provider_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("السعر يجب أن يكون أكبر من 0.")
        return value
    
    def validate(self, attrs):
        request_obj = self.context['custom_request']
        provider    = self.context['request'].user
 
        # الطلب لازم يكون published أو offers_received
        if request_obj.status not in ('published', 'offers_received'):
            raise serializers.ValidationError(
                "لا يمكن إرسال عرض على هذا الطلب."
            )
 
        # الفني مبعتش عرض قبل كده
        if ServiceOffer.objects.filter(
            request=request_obj, provider=provider
        ).exists():
            raise serializers.ValidationError(
                "لقد أرسلت عرضاً على هذا الطلب من قبل."
            )
 
        address = request_obj.address
        if not address or address.lat is None or address.lng is None:
            raise serializers.ValidationError(
                "لا يمكن إرسال عرض على هذا الطلب (العنوان غير مكتمل)."
            )
 
        provider_address = get_provider_default_address(provider)
        if not provider_address:
            raise serializers.ValidationError(
                "يجب إضافة عنوان افتراضي بإحداثيات أولاً قبل إرسال عروض."
            )
 
        distance = haversine_km(
            provider_address.lat, provider_address.lng,
            address.lat, address.lng
        )
        if distance > DEFAULT_SERVICE_RADIUS_KM:
            raise serializers.ValidationError(
                "لا يمكنك إرسال عرض خارج نطاق منطقتك."
            )
 
        return attrs
    def create(self, validated_data):
        request_obj = self.context['custom_request']
        provider    = self.context['request'].user

        offer = ServiceOffer.objects.create(
            request=request_obj,
            provider=provider,
            **validated_data
        )

        # حدّث ستاتوس الطلب لو أول عرض
        if request_obj.status == 'published':
            request_obj.status = 'offers_received'
            request_obj.save(update_fields=['status'])

        return offer


class ServiceOfferAdminSerializer(serializers.ModelSerializer):
    """للأدمن — كل التفاصيل"""
    provider_name  = serializers.CharField(source='provider.name',         read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)

    class Meta:
        model  = ServiceOffer
        fields = [
            'id', 'provider_name', 'provider_phone',
            'provider_price', 'platform_fee', 'final_price',
            'note', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


# ==================== REQUEST CHAT ====================

class RequestChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestChat
        fields = [
            'id', 'request', 'sender_type', 'sender_id',
            'message', 'message_type',
            'attachment_url', 'attachment_duration',
            'file_name', 'file_size',
            'is_read', 'read_at', 'created_at',
        ]

MAX_ATTACHMENT_SIZES = {
    'image': 10 * 1024 * 1024,   # 10MB
    'voice': 15 * 1024 * 1024,   # 15MB
    'file': 25 * 1024 * 1024,    # 25MB
}


class RequestChatCreateSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)
    message_type = serializers.ChoiceField(
        choices=RequestChat.MESSAGE_TYPE_CHOICES, required=False, default='text'
    )

    def validate(self, attrs):
        request = self.context['request']
        message_type = attrs.get('message_type', 'text')
        message_text = (attrs.get('message') or '').strip()
        attachment_file = request.FILES.get('attachment')

        if message_type == 'text':
            if not message_text:
                raise serializers.ValidationError({'message': 'نص الرسالة مطلوب.'})
        else:
            if not attachment_file:
                raise serializers.ValidationError(
                    {'attachment': 'الملف مطلوب لهذا النوع من الرسائل.'}
                )

            max_size = MAX_ATTACHMENT_SIZES.get(message_type)
            if max_size and attachment_file.size > max_size:
                raise serializers.ValidationError(
                    {'attachment': f'حجم الملف أكبر من الحد المسموح ({max_size // (1024*1024)}MB).'}
                )

            content_type = attachment_file.content_type or ''
            if message_type == 'image' and not content_type.startswith('image/'):
                raise serializers.ValidationError({'attachment': 'الملف المرفوع ليس صورة صالحة.'})
            if message_type == 'voice' and not content_type.startswith('audio/'):
                raise serializers.ValidationError({'attachment': 'الملف المرفوع ليس تسجيل صوتي صالح.'})

        attrs['message_text'] = message_text
        attrs['attachment_file'] = attachment_file
        attrs['message_type'] = message_type
        return attrs

    def create(self, validated_data):
        from utils.cloudinary import upload_image, upload_audio, upload_raw

        request = self.context['request']
        custom_request = self.context['custom_request']
        user_type = self.context['user_type']
        user = request.user

        message_type = validated_data['message_type']
        message_text = validated_data['message_text']
        attachment_file = validated_data['attachment_file']

        attachment_url = None
        attachment_duration = None
        file_name = None
        file_size = None

        if attachment_file:
            file_name = attachment_file.name
            file_size = attachment_file.size

            if message_type == 'image':
                attachment_url = upload_image(attachment_file, folder="chat_attachments")
            elif message_type == 'voice':
                result = upload_audio(attachment_file, folder="chat_voice_notes")
                attachment_url = result['url']
                attachment_duration = result.get('duration')
            elif message_type == 'file':
                attachment_url = upload_raw(attachment_file, folder="chat_files")

        return RequestChat.objects.create(
            request=custom_request,
            sender_type=user_type,
            sender_id=user.id,
            message=message_text or None,
            message_type=message_type,
            attachment_url=attachment_url,
            attachment_duration=attachment_duration,
            file_name=file_name,
            file_size=file_size,
        )
# ==================== STATUS UPDATE (ADMIN) ====================

class CustomRequestStatusUpdateSerializer(serializers.Serializer):
    VALID_TRANSITIONS = {
        'published':       ['cancelled', 'expired'],
        'offers_received': ['cancelled', 'expired'],
        'accepted':        ['in_progress', 'cancelled'],
        'in_progress':     ['completed'],
        'completed':       [],
        'cancelled':       [],
        'expired':         [],
    }

    status = serializers.ChoiceField(choices=CustomRequest.STATUS_CHOICES)

    def validate(self, attrs):
        req        = self.context['custom_request']
        new_status = attrs['status']
        allowed    = self.VALID_TRANSITIONS.get(req.status, [])

        if new_status not in allowed:
            raise serializers.ValidationError(
                f"لا يمكن الانتقال من '{req.status}' إلى '{new_status}'. "
                f"المسموح: {allowed}"
            )
        return attrs
    

from .models import Notification
 
 
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'event', 'title', 'body', 'data',
            'is_read', 'created_at', 'read_at'
        ]
        read_only_fields = fields


"""
إضافة في custom_services/serializers.py
"""

from .models import DeviceToken


class DeviceTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)

    def validate_token(self, value):
        if not value.strip():
            raise serializers.ValidationError("التوكن لا يمكن أن يكون فارغاً.")
        return value.strip()
    

class ProviderMyOfferSerializer(serializers.ModelSerializer):
    """
    للفني — يشوف كل عروضه (على كل الطلبات) وحالة كل عرض:
    pending / accepted / rejected / withdrawn
    """
    request_id           = serializers.UUIDField(source='request.id', read_only=True)
    request_title        = serializers.CharField(source='request.title', read_only=True)
    request_status       = serializers.CharField(source='request.status', read_only=True)
    specialization_name  = serializers.CharField(
        source='request.specialization.name', read_only=True
    )
    city     = serializers.CharField(source='request.address.city',     read_only=True)
    region   = serializers.CharField(source='request.address.region',   read_only=True)
    is_accepted = serializers.SerializerMethodField()

    def get_is_accepted(self, obj):
        return obj.status == 'accepted'

    class Meta:
        model  = ServiceOffer
        fields = [
            'id',
            'request_id', 'request_title', 'request_status',
            'specialization_name', 'city', 'region',
            'provider_price', 'final_price', 'note',
            'status', 'is_accepted',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ServiceOfferUpdateSerializer(serializers.Serializer):
    """الفني يعدل عرضه، بس لو لسه pending"""
    provider_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    note           = serializers.CharField(required=False, allow_blank=True)

    def validate_provider_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("السعر يجب أن يكون أكبر من 0.")
        return value

    def validate(self, attrs):
        offer = self.context['offer']
        if offer.status != 'pending':
            raise serializers.ValidationError(
                "لا يمكن تعديل العرض بعد أن تغيرت حالته."
            )
        if not attrs:
            raise serializers.ValidationError("لا توجد بيانات للتعديل.")
        return attrs

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=list(validated_data.keys()) + ['updated_at'])
        return instance
    
class ProviderCustomCompletionFormListSerializer(serializers.Serializer):
    id                  = serializers.UUIDField()
    request_id          = serializers.SerializerMethodField()
    request_title       = serializers.SerializerMethodField()
    specialization_name = serializers.SerializerMethodField()
    customer_address    = serializers.SerializerMethodField()
    final_price         = serializers.SerializerMethodField()
    payment_request_id  = serializers.SerializerMethodField()  # ← جديد
    payment_status      = serializers.SerializerMethodField()  # ← جديد (مفيد للفلاتر يعرض حالة الدفع في نفس الكارت)
    status              = serializers.CharField()
    is_finished         = serializers.BooleanField()
    started_at          = serializers.DateTimeField()
    finished_at         = serializers.DateTimeField()
    created_at          = serializers.DateTimeField()

    def get_request_id(self, obj):
        return str(obj.custom_request_id) if obj.custom_request_id else None

    def get_request_title(self, obj):
        return obj.custom_request.title if obj.custom_request else None

    def get_specialization_name(self, obj):
        if obj.custom_request and obj.custom_request.specialization:
            return obj.custom_request.specialization.name
        return None

    def get_customer_address(self, obj):
        address = obj.custom_request.address if obj.custom_request else None
        if not address:
            return None
        return {
            'id': str(address.id),
            'city': address.city.name if address.city else None,
            'region': address.region.name if address.region else None,
            'district': address.district,
            'street': address.street,
            'building_no': address.building_no,
            'floor_no': address.floor_no,
            'apartment_no': address.apartment_no,
            'label': address.label,
            'lat': str(address.lat) if address.lat is not None else None,
            'lng': str(address.lng) if address.lng is not None else None,
        }

    def get_final_price(self, obj):
        if not obj.custom_request:
            return None
        accepted_offer = obj.custom_request.offers.filter(status='accepted').first()
        return str(accepted_offer.final_price) if accepted_offer else None

    def get_payment_request_id(self, obj):
        """
        لو الـ completion form ده اتعمله finish بالفعل، هيكون فيه
        PaymentRequest مربوط بيه (OneToOne). الفني محتاج الـ id ده
        عشان ينادي confirm-cash/ لو العميل اختار الدفع كاش.
        """
        payment_request = getattr(obj, 'payment_request', None)
        return str(payment_request.id) if payment_request else None

    def get_payment_status(self, obj):
        """
        حالة الدفع الحالية — مفيدة للفلاتر يعرض تاج/badge في الكارت
        (مثلاً "بانتظار اختيار طريقة الدفع" أو "بانتظار تأكيد الكاش")
        من غير ما يحتاج نداء API إضافي منفصل.
        """
        payment_request = getattr(obj, 'payment_request', None)
        return payment_request.status if payment_request else None
    




class OnboardingSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OnboardingSlide
        fields = ['id', 'image', 'title', 'description', 'order']
        read_only_fields = fields


from .models import AppMessage


class AppMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AppMessage
        fields = ['id', 'title', 'body', 'image', 'link', 'priority', 'created_at']
        read_only_fields = fields

class AppMessageAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AppMessage
        fields = [
            'id', 'audience', 'title', 'body', 'image', 'link',
            'is_active', 'priority', 'start_at', 'end_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OnboardingSlideAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OnboardingSlide
        fields = [
            'id', 'image', 'title', 'description',
            'order', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationSerializer(serializers.Serializer):
    """
    يمثل محادثة واحدة = طلب مخصص واحد له فني مقبول وفيه رسائل شات.
    """
    request_id = serializers.UUIDField(source='id')
    request_title = serializers.CharField(source='title')
    request_status = serializers.CharField(source='status')

    provider_id = serializers.UUIDField(source='accepted_provider.id')
    provider_name = serializers.CharField(source='accepted_provider.name')
    provider_rating = serializers.DecimalField(
        source='accepted_provider.average_rating',
        max_digits=3, decimal_places=2, required=False
    )

    last_message = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    last_message_sender_type = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField()

    def get_last_message(self, obj):
        last = getattr(obj, '_last_message', None)
        return last.message if last else None

    def get_last_message_at(self, obj):
        last = getattr(obj, '_last_message', None)
        return last.created_at.isoformat() if last else None

    def get_last_message_sender_type(self, obj):
        last = getattr(obj, '_last_message', None)
        return last.sender_type if last else None