from rest_framework import serializers
from .models import (
    ExistedService, ServiceAttribute, Booking, PreviousWork,
    ServiceReview, ServiceProvider, Specialization, Warranty,
    ServiceCompletionForm, CompletionMedia,
)
from accounts.serializers import SpecializationSerializer
from accounts.serializers import CustomerAddressSerializer
from accounts.models import CustomerAddress

# ==================== WARRANTY SERIALIZERS ====================

class WarrantySerializer(serializers.ModelSerializer):
    """للكلاينت - يشوف ضمان الخدمة"""
    class Meta:
        model = Warranty
        fields = ['id', 'duration_value', 'duration_type', 'notes']
        read_only_fields = fields


class WarrantyWriteSerializer(serializers.ModelSerializer):
    """للأدمن - إنشاء أو تعديل"""
    class Meta:
        model = Warranty
        fields = ['duration_value', 'duration_type', 'notes']

    def validate_duration_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration value must be greater than 0.")
        return value


# ==================== ATTRIBUTE SERIALIZERS (وصفية بس) ====================

class ServiceAttributeSerializer(serializers.ModelSerializer):
    """للكلاينت"""
    class Meta:
        model  = ServiceAttribute
        fields = ['id', 'name', 'details']
        read_only_fields = ['id']


class ServiceAttributeAdminSerializer(serializers.ModelSerializer):
    """للأدمن"""
    class Meta:
        model  = ServiceAttribute
        fields = ['id', 'name', 'details', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceAttributeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ServiceAttribute
        fields = ['name', 'details']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()


# ==================== SERVICE SERIALIZERS ====================

class ExistedServiceListSerializer(serializers.ModelSerializer):
    """للكلاينت - قائمة خفيفة"""
    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'date', 'is_active', 'visit_cost']
        read_only_fields = ['id']


class ExistedServiceDetailSerializer(serializers.ModelSerializer):
    """للكلاينت - تفاصيل مع الـ attributes والضمان"""
    attributes = ServiceAttributeSerializer(many=True, read_only=True)
    warranty   = WarrantySerializer(read_only=True)

    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'details', 'date',
                  'is_active', 'attributes', 'warranty', 'visit_cost']
        read_only_fields = ['id']


class ExistedServiceAdminListSerializer(serializers.ModelSerializer):
    attributes_count = serializers.IntegerField(source='attributes.count', read_only=True)
    specialization = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        required=False,
        allow_null=True
    )
    warranty = WarrantySerializer(read_only=True)

    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'date', 'is_active',
                  'attributes_count', 'specialization',
                  'created_at', 'updated_at', 'warranty', 'visit_cost']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExistedServiceAdminDetailSerializer(serializers.ModelSerializer):
    """للأدمن - تفاصيل كاملة"""
    attributes = ServiceAttributeAdminSerializer(many=True, read_only=True)
    specialization = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'specialization', 'details', 'date',
                  'is_active', 'attributes', 'created_at', 'updated_at',
                  'warranty', 'visit_cost']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExistedServiceWriteSerializer(serializers.ModelSerializer):
    warranty = WarrantyWriteSerializer(required=False, allow_null=True)

    class Meta:
        model  = ExistedService
        fields = ['title', 'image', 'details', 'date', 'is_active', 'specialization', 'warranty', 'visit_cost']

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()

    def create(self, validated_data):
        warranty_data = validated_data.pop('warranty', None)
        service = ExistedService.objects.create(**validated_data)
        if warranty_data:
            Warranty.objects.create(service=service, **warranty_data)
        return service

    def update(self, instance, validated_data):
        warranty_data = validated_data.pop('warranty', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if warranty_data is None:
            if hasattr(instance, 'warranty'):
                instance.warranty.delete()
        else:
            Warranty.objects.update_or_create(
                service=instance,
                defaults=warranty_data
            )

        return instance


# ==================== BOOKING SERIALIZERS - CLIENT ====================

class BookingCreateSerializer(serializers.Serializer):
    """
    الحجز دلوقتي بيتعمل بدون كمية وبدون سعر.
    السعر بيتحدد لاحقاً يدوياً بعد تواصل الدعم الفني مع العميل والفني.
    """
    service_id     = serializers.UUIDField()
    scheduled_date = serializers.DateField()
    notes          = serializers.CharField(required=False, allow_blank=True, default='')

    address_id   = serializers.UUIDField(required=False)
    address_data = CustomerAddressSerializer(required=False)

    def validate_service_id(self, value):
        if not ExistedService.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Service not found.")
        return value

    def validate(self, attrs):
        if not attrs.get('address_id') and not attrs.get('address_data'):
            raise serializers.ValidationError("Either address_id or address_data is required.")
        return attrs

    def create(self, validated_data):
        customer     = self.context['request'].user
        service      = ExistedService.objects.get(id=validated_data.pop('service_id'))
        address_id   = validated_data.pop('address_id', None)
        address_data = validated_data.pop('address_data', None)

        if address_data:
            address = CustomerAddress.objects.create(customer=customer, **address_data)
        else:
            address = CustomerAddress.objects.get(id=address_id)

        booking = Booking.objects.create(
            customer=customer,
            service=service,
            address=address,
            provider=None,
            **validated_data
        )
        return booking


class BookingSerializer(serializers.ModelSerializer):
    service_title  = serializers.CharField(source='service.title', read_only=True)
    service_visit_cost = serializers.DecimalField(
        source='service.visit_cost',
        max_digits=10, decimal_places=2,
        read_only=True, allow_null=True
    )
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    address        = CustomerAddressSerializer(read_only=True)

    class Meta:
        model  = Booking
        fields = [
            'id', 'service_title', 'address', 'scheduled_date',
            'notes', 'status', 'service_visit_cost',
            'price', 'priced_at',
            'created_at', 'provider_name', 'provider_phone'
        ]
        read_only_fields = fields


class BookingCancelSerializer(serializers.Serializer):
    """إلغاء حجز لسه في حالة pending (قبل ما الدعم يبدأ التواصل)"""
    def validate(self, attrs):
        booking = self.context['booking']
        if booking.status != 'pending':
            raise serializers.ValidationError("You can only cancel a pending booking.")
        return attrs


class BookingPriceDecisionSerializer(serializers.Serializer):
    """
    العميل بيوافق أو يرفض السعر المقترح (price_proposed).
    موافقة → confirmed | رفض → cancelled
    """
    accept = serializers.BooleanField()

    def validate(self, attrs):
        booking = self.context['booking']
        if booking.status != 'price_proposed':
            raise serializers.ValidationError("No price is currently awaiting your decision.")
        return attrs

    def save(self):
        booking = self.context['booking']
        booking.status = 'confirmed' if self.validated_data['accept'] else 'cancelled'
        booking.save(update_fields=['status'])
        return booking


# ==================== BOOKING SERIALIZERS - ADMIN ====================

class BookingAdminSerializer(serializers.ModelSerializer):
    service_title  = serializers.CharField(source='service.title', read_only=True)
    service_visit_cost = serializers.DecimalField(
        source='service.visit_cost',
        max_digits=10, decimal_places=2,
        read_only=True, allow_null=True
    )
    customer_name  = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True)
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    address = CustomerAddressSerializer(read_only=True)

    class Meta:
        model  = Booking
        fields = [
            'id', 'customer_name', 'customer_phone', 'service_visit_cost',
            'service_title', 'address', 'scheduled_date', 'service_id',
            'notes', 'status', 'price', 'priced_at',
            'created_at', 'updated_at', 'provider_name', 'provider_phone'
        ]
        read_only_fields = fields


class BookingStatusUpdateSerializer(serializers.Serializer):
    """
    انتقالات الحالة العامة (بدون سعر). تحويل السعر نفسه بيتم من
    BookingSetPriceSerializer و BookingPriceDecisionSerializer بس.
    """
    VALID_TRANSITIONS = {
        'pending':         ['awaiting_price', 'cancelled'],
        'awaiting_price':  ['cancelled'],
        'price_proposed':  [],
        'confirmed':       ['completed', 'cancelled'],
        'completed':       [],
        'cancelled':       [],
    }

    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)

    def validate(self, attrs):
        booking    = self.context['booking']
        new_status = attrs['status']
        allowed    = self.VALID_TRANSITIONS.get(booking.status, [])

        if new_status not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from '{booking.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        return attrs


class BookingSetPriceSerializer(serializers.Serializer):
    """
    الأدمن بيحط السعر بعد ما يتواصل مع الفني تليفونياً.
    مسموح بس لو الحجز في awaiting_price.
    awaiting_price → price_proposed
    """
    price = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate(self, attrs):
        booking = self.context['booking']
        if booking.status != 'awaiting_price':
            raise serializers.ValidationError(
                "You can only set a price for a booking that is awaiting_price."
            )
        return attrs

    def save(self):
        from django.utils import timezone
        booking = self.context['booking']
        booking.price     = self.validated_data['price']
        booking.status    = 'price_proposed'
        booking.priced_at = timezone.now()
        booking.save(update_fields=['price', 'status', 'priced_at'])
        return booking


# ==================== REVIEW SERIALIZERS ====================

class ServiceReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ServiceReview
        fields = ['stars', 'comment']

    def validate_stars(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Stars must be between 1 and 5.")
        return value

    def create(self, validated_data):
        service  = self.context['service']
        customer = self.context['request'].user

        review, _ = ServiceReview.objects.update_or_create(
            service=service,
            customer=customer,
            defaults=validated_data
        )
        return review


class ServiceReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model  = ServiceReview
        fields = ['id', 'customer_name', 'stars', 'comment', 'created_at']
        read_only_fields = fields


class ServiceRatingSummarySerializer(serializers.Serializer):
    service_id    = serializers.UUIDField()
    service_title = serializers.CharField()
    average_stars = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_reviews = serializers.IntegerField()
    stars_breakdown = serializers.DictField()


# ==================== SERVICE PROVIDER SERIALIZERS ====================

class ServiceProviderSerializer(serializers.ModelSerializer):
    provider_id   = serializers.UUIDField(source='provider.id', read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    average_rating = serializers.DecimalField(
        source='provider.average_rating',
        max_digits=3, decimal_places=2, read_only=True
    )
    total_reviews  = serializers.IntegerField(source='provider.total_reviews', read_only=True)
    specialization = serializers.SerializerMethodField()

    def get_specialization(self, obj):
        spec = obj.provider.specialization
        if spec:
            return {'id': str(spec.id), 'name': spec.name}
        return None

    class Meta:
        model  = ServiceProvider
        fields = [
            'id', 'provider_id', 'provider_name', 'provider_phone',
            'specialization', 'average_rating', 'total_reviews', 'is_available'
        ]
        read_only_fields = fields


class ServiceProviderAdminSerializer(serializers.ModelSerializer):
    provider_id    = serializers.UUIDField(source='provider.id', read_only=True)
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    is_approved    = serializers.BooleanField(source='provider.is_approved', read_only=True)
    average_rating = serializers.DecimalField(
        source='provider.average_rating',
        max_digits=3, decimal_places=2, read_only=True
    )

    class Meta:
        model  = ServiceProvider
        fields = [
            'id', 'provider_id', 'provider_name', 'provider_phone',
            'is_approved', 'average_rating', 'is_available', 'created_at'
        ]
        read_only_fields = fields


class AssignProviderSerializer(serializers.Serializer):
    provider_id = serializers.UUIDField()

    def validate_provider_id(self, value):
        from accounts.models import Provider
        try:
            Provider.objects.get(id=value, is_approved=True, is_active=True)
        except Provider.DoesNotExist:
            raise serializers.ValidationError("Provider not found or not approved.")
        return value

    def validate(self, attrs):
        service     = self.context['service']
        provider_id = attrs['provider_id']

        if ServiceProvider.objects.filter(
            service=service, provider_id=provider_id
        ).exists():
            raise serializers.ValidationError("This provider is already assigned to this service.")
        return attrs

    def create(self, validated_data):
        service = self.context['service']
        return ServiceProvider.objects.create(
            service=service,
            provider_id=validated_data['provider_id']
        )


# ==================== COMPLETION FORM SERIALIZERS ====================

class CompletionMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompletionMedia
        fields = ['id', 'media_type', 'media_url', 'thumbnail_url', 'created_at']
        read_only_fields = ['id', 'created_at']


class CompletionMediaWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompletionMedia
        fields = ['media_type', 'media_url', 'thumbnail_url']

    def validate(self, attrs):
        if attrs.get('media_type') == 'video' and not attrs.get('thumbnail_url'):
            raise serializers.ValidationError("thumbnail_url is required for videos.")
        return attrs


class ServiceCompletionFormSerializer(serializers.ModelSerializer):
    media               = CompletionMediaSerializer(many=True, read_only=True)
    booking_id          = serializers.UUIDField(source='booking.id', read_only=True)
    previous_work       = serializers.SerializerMethodField()
    payment_request_id  = serializers.SerializerMethodField()
    payment_status      = serializers.SerializerMethodField()

    class Meta:
        model  = ServiceCompletionForm
        fields = [
            'id', 'booking_id', 'notes',
            'status', 'started_at',
            'is_finished', 'finished_at',
            'media', 'previous_work',
            'payment_request_id', 'payment_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_previous_work(self, obj):
        try:
            work = obj.previous_work
        except PreviousWork.DoesNotExist:
            return None
        return PreviousWorkSerializer(work).data

    def get_payment_request_id(self, obj):
        payment_request = getattr(obj, 'payment_request', None)
        return str(payment_request.id) if payment_request else None

    def get_payment_status(self, obj):
        payment_request = getattr(obj, 'payment_request', None)
        return payment_request.status if payment_request else None


class ServiceCompletionFormUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ServiceCompletionForm
        fields = ['notes', 'is_finished']

    def validate(self, attrs):
        form = self.instance
        if form.is_finished:
            raise serializers.ValidationError("This completion form is already finished.")
        return attrs

    def update(self, instance, validated_data):
        is_finishing = validated_data.get('is_finished', False)
        instance.notes = validated_data.get('notes', instance.notes)

        if is_finishing:
            from django.utils import timezone
            instance.is_finished = True
            instance.finished_at = timezone.now()

        instance.save()
        return instance


# ==================== PREVIOUS WORK SERIALIZERS ====================

class PreviousWorkSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PreviousWork
        fields = ['id', 'before_image', 'after_image', 'created_at']
        read_only_fields = fields


class PreviousWorkWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PreviousWork
        fields = ['before_image', 'after_image']
        extra_kwargs = {
            'before_image': {'required': False},
            'after_image':  {'required': False},
        }

    def validate(self, attrs):
        form = self.context['form']
        if hasattr(form, 'previous_work'):
            raise serializers.ValidationError(
                "This completion form already has a previous work entry."
            )
        if not self.instance and not attrs.get('before_image'):
            raise serializers.ValidationError(
                "before_image is required when creating a previous work entry."
            )
        return attrs

    def create(self, validated_data):
        form = self.context['form']
        service = form.booking.service if form.booking else None
        return PreviousWork.objects.create(
            service=service,
            completion_form=form,
            **validated_data
        )


# ==================== PROVIDER COMPLETION FORM LIST ====================

class ServiceAttributeInlineSerializer(serializers.Serializer):
    """وصف مواصفات الخدمة (بدون كمية) — بيظهر للفني كمرجع وقت التسعير/التنفيذ"""
    name    = serializers.CharField()
    details = serializers.CharField()


class ProviderCompletionFormListSerializer(serializers.Serializer):
    id                = serializers.UUIDField()
    booking_id        = serializers.SerializerMethodField()
    service_title     = serializers.SerializerMethodField()
    customer_address  = serializers.SerializerMethodField()
    price             = serializers.SerializerMethodField()
    is_finished       = serializers.BooleanField()
    finished_at       = serializers.DateTimeField()
    created_at        = serializers.DateTimeField()
    service_attributes = serializers.SerializerMethodField()

    def get_booking_id(self, obj):
        return str(obj.booking_id) if obj.booking_id else None

    def get_service_title(self, obj):
        if obj.booking and obj.booking.service:
            return obj.booking.service.title
        return None

    def get_price(self, obj):
        return obj.booking.price if obj.booking else None

    def get_customer_address(self, obj):
        address = obj.booking.address if obj.booking else None
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

    def get_service_attributes(self, obj):
        if not obj.booking or not obj.booking.service:
            return []
        attributes = obj.booking.service.attributes.all()
        return ServiceAttributeInlineSerializer(attributes, many=True).data
    

class AdminConfirmPriceOnBehalfSerializer(serializers.Serializer):
    """
    الأدمن بيأكد أو يرفض السعر بالنيابة عن العميل — مثلاً لو العميل
    وافق تليفونيًا وعايز الأدمن يسجلها يدويًا في النظام.
    accept=True  → confirmed
    accept=False → cancelled
    """
    accept = serializers.BooleanField()

    def validate(self, attrs):
        booking = self.context['booking']
        if booking.status != 'price_proposed':
            raise serializers.ValidationError(
                "الحجز مش في حالة انتظار موافقة العميل."
            )
        return attrs

    def save(self):
        booking = self.context['booking']
        booking.status = 'confirmed' if self.validated_data['accept'] else 'cancelled'
        booking.save(update_fields=['status'])
        return booking