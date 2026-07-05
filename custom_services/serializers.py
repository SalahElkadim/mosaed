from rest_framework import serializers
from django.utils import timezone

from accounts.models import CustomerAddress, Provider, Specialization
from accounts.serializers import CustomerAddressSerializer, SpecializationSerializer

from .models import CustomRequest, ServiceOffer, RequestChat, PlatformSettings


# ==================== PLATFORM SETTINGS ====================

class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlatformSettings
        fields = ['key', 'value', 'updated_at']
        read_only_fields = ['key', 'updated_at']


# ==================== CUSTOM REQUEST ====================

class CustomRequestCreateSerializer(serializers.Serializer):
    """العميل ينشر طلب جديد"""
    specialization_id = serializers.UUIDField()
    title             = serializers.CharField(max_length=255)
    description       = serializers.CharField()
    image             = serializers.URLField(required=False, allow_blank=True)
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
        fields = ['title', 'description', 'image', 'specialization', 'scheduled_date']

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

    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'specialization_name',
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

    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'description', 'image',
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

    def get_my_offer(self, obj):
        provider = self.context['request'].user
        offer    = obj.offers.filter(provider=provider).first()
        if offer:
            return ServiceOfferSerializer(offer).data
        return None

    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'title', 'description', 'image',
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

    class Meta:
        model  = CustomRequest
        fields = [
            'id', 'customer_name', 'customer_phone',
            'title', 'description', 'image',
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
        model  = RequestChat
        fields = ['id', 'sender_type', 'sender_id', 'message', 'is_read', 'read_at', 'created_at']
        read_only_fields = fields


class RequestChatCreateSerializer(serializers.Serializer):
    message = serializers.CharField()

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("الرسالة لا يمكن أن تكون فارغة.")
        return value.strip()

    def validate(self, attrs):
        custom_request = self.context['custom_request']
        user_type      = self.context['user_type']
        user           = self.context['request'].user

        # الشات متاح بس بعد القبول
        if custom_request.status not in ('accepted', 'in_progress', 'completed'):
            raise serializers.ValidationError(
                "الشات متاح فقط بعد قبول العرض."
            )

        # التحقق إن المتكلم هو العميل أو الفني المقبول بس
        if user_type == 'customer':
            if custom_request.customer_id != user.id:
                raise serializers.ValidationError("غير مصرح.")
        elif user_type == 'provider':
            if custom_request.accepted_provider_id != user.id:
                raise serializers.ValidationError(
                    "فقط الفني المقبول يمكنه المشاركة في الشات."
                )

        return attrs

    def create(self, validated_data):
        custom_request = self.context['custom_request']
        user_type      = self.context['user_type']
        user           = self.context['request'].user

        return RequestChat.objects.create(
            request=custom_request,
            sender_type=user_type,
            sender_id=user.id,
            message=validated_data['message']
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