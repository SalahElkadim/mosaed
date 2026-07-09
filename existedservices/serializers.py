from rest_framework import serializers
from .models import ExistedService, ServiceAttribute, Booking, PreviousWork,BookingItem, ServiceReview, ServiceProvider, Specialization, Warranty, ServiceCompletionForm, CompletionMedia
from accounts.serializers import SpecializationSerializer  # Import SpecializationSerializer
from accounts.serializers import CustomerAddressSerializer
from accounts.models import CustomerAddress
from .models import Coupon  # Import the Coupon model
# ==================== ATTRIBUTE SERIALIZERS ====================
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
    
class ServiceAttributeSerializer(serializers.ModelSerializer):
    """للكلاينت"""
    class Meta:
        model  = ServiceAttribute
        fields = ['id', 'name', 'details', 'unit_cost', 'unit_name', 'quantity_name']
        read_only_fields = ['id']


class ServiceAttributeAdminSerializer(serializers.ModelSerializer):
    """للأدمن"""
    class Meta:
        model  = ServiceAttribute
        fields = ['id', 'name', 'details', 'unit_cost', 'unit_name', 'quantity_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceAttributeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ServiceAttribute
        fields = ['name', 'details', 'unit_cost', 'unit_name', 'quantity_name']

    def validate_unit_cost(self, value):
        if value <= 0:
            raise serializers.ValidationError("Unit cost must be greater than 0.")
        return value


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
    warranty   = WarrantySerializer(read_only=True)          # ← أضف السطر ده

    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'details', 'date', 
                  'is_active', 'attributes', 'warranty', 'visit_cost']     # ← أضف warranty
        read_only_fields = ['id']


class ExistedServiceAdminListSerializer(serializers.ModelSerializer):
    attributes_count = serializers.IntegerField(source='attributes.count', read_only=True)
    specialization = serializers.PrimaryKeyRelatedField(
    queryset=Specialization.objects.all(),
    required=False,
    allow_null=True
)  # ← أضف السطر ده
    warranty   = WarrantySerializer(read_only=True)
    class Meta:
        model  = ExistedService
        fields = ['id', 'title', 'image', 'date', 'is_active', 
                  'attributes_count', 'specialization',  # ← أضفه هنا
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
        fields = ['id', 'title', 'image','specialization', 'details', 'date', 'is_active', 'attributes', 'created_at', 'updated_at', 'warranty', 'visit_cost']
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
            # لو بعت warranty: null → احذف الضمان لو موجود
            if hasattr(instance, 'warranty'):
                instance.warranty.delete()
        else:
            Warranty.objects.update_or_create(
                service=instance,
                defaults=warranty_data
            )

        return instance


# ==================== BOOKING ITEM SERIALIZERS ====================

class BookingItemCreateSerializer(serializers.Serializer):
    attribute_id = serializers.UUIDField()
    value        = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Value must be greater than 0.")
        return value


class BookingItemSerializer(serializers.ModelSerializer):
    attribute_name     = serializers.CharField(source='attribute.name', read_only=True)
    unit_cost_snapshot = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = BookingItem
        fields = ['id', 'attribute_name', 'value', 'unit_cost_snapshot', 'cost']
        read_only_fields = fields


# ==================== BOOKING SERIALIZERS - CLIENT ====================
class BookingCreateSerializer(serializers.Serializer):
    service_id     = serializers.UUIDField()
    scheduled_date = serializers.DateField()
    notes          = serializers.CharField(required=False, allow_blank=True, default='')
    items          = BookingItemCreateSerializer(many=True)
    coupon_code    = serializers.CharField(required=False, allow_blank=True, default='')  # ← جديد

    address_id   = serializers.UUIDField(required=False)
    address_data = CustomerAddressSerializer(required=False)

    def validate(self, attrs):
        # ... الـ validation الموجود ...
        return attrs

    def create(self, validated_data):
        customer     = self.context['request'].user
        items_data   = validated_data.pop('items')
        service      = ExistedService.objects.get(id=validated_data.pop('service_id'))
        address_id   = validated_data.pop('address_id', None)
        address_data = validated_data.pop('address_data', None)
        coupon_code  = validated_data.pop('coupon_code', '').strip().upper()

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

        for item_data in items_data:
            attribute = ServiceAttribute.objects.get(id=item_data['attribute_id'])
            BookingItem.objects.create(
                booking=booking,
                attribute=attribute,
                value=item_data['value'],
                unit_cost_snapshot=attribute.unit_cost,
            )

        booking.calculate_total()

        # ── تطبيق الكوبون ──
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                valid, _ = coupon.is_valid()
                if valid:
                    if not coupon.service or coupon.service == service:
                        if not coupon.min_booking_cost or booking.total_cost >= coupon.min_booking_cost:
                            discount = coupon.calc_discount(booking.total_cost)
                            booking.coupon          = coupon
                            booking.discount_amount = discount
                            booking.final_cost      = booking.total_cost - discount
                            booking.save(update_fields=['coupon', 'discount_amount', 'final_cost'])
                            coupon.used_count += 1
                            coupon.save(update_fields=['used_count'])
            except Coupon.DoesNotExist:
                pass
        else:
            booking.final_cost = booking.total_cost
            booking.save(update_fields=['final_cost'])

        return booking

class BookingSerializer(serializers.ModelSerializer):
    items          = BookingItemSerializer(many=True, read_only=True)
    service_title  = serializers.CharField(source='service.title', read_only=True)
    service_visit_cost = serializers.DecimalField(  # ← جديد
        source='service.visit_cost', 
        max_digits=10, decimal_places=2, 
        read_only=True, allow_null=True
    )
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    address        = CustomerAddressSerializer(read_only=True)
    coupon_code    = serializers.CharField(source='coupon.code', read_only=True)  # ← جديد

    class Meta:
        model  = Booking
        fields = [
            'id', 'service_title', 'address', 'scheduled_date',
            'notes', 'status', 'total_cost',"service_visit_cost",
            'coupon_code', 'discount_amount', 'final_cost',   # ← جديد
            'items', 'created_at', 'provider_name', 'provider_phone'
        ]
        read_only_fields = fields


class BookingCancelSerializer(serializers.Serializer):
    def validate(self, attrs):
        booking = self.context['booking']
        if booking.status != 'pending':
            raise serializers.ValidationError("You can only cancel a pending booking.")
        return attrs


# ==================== BOOKING SERIALIZERS - ADMIN ====================

class BookingAdminSerializer(serializers.ModelSerializer):
    items          = BookingItemSerializer(many=True, read_only=True)
    service_title  = serializers.CharField(source='service.title', read_only=True)
    service_visit_cost = serializers.DecimalField(  # ← جديد
        source='service.visit_cost',
        max_digits=10, decimal_places=2,
        read_only=True, allow_null=True
    )
    customer_name  = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True)
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)
    address = CustomerAddressSerializer(read_only=True)
    coupon_code    = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model  = Booking
        fields = [
            'id', 'customer_name', 'customer_phone','service_visit_cost',
            'service_title', 'address', 'scheduled_date','service_id',
            'notes', 'status', 'total_cost','coupon_code', 'discount_amount', 'final_cost',
            'items', 'created_at', 'updated_at','provider_name', 'provider_phone'
        ]
        read_only_fields = fields


class BookingStatusUpdateSerializer(serializers.Serializer):
    VALID_TRANSITIONS = {
        'pending':   ['confirmed', 'cancelled'],
        'confirmed': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
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
 
        # لو عنده review قديم على نفس الـ service → update
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
    """متوسط التقييمات وعددهم"""
    service_id    = serializers.UUIDField()
    service_title = serializers.CharField()
    average_stars = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_reviews = serializers.IntegerField()
    stars_breakdown = serializers.DictField()  # {"5": 10, "4": 5, ...}


class ServiceProviderSerializer(serializers.ModelSerializer):
    """للعميل — يشوف الفنيين المتاحين للخدمة"""
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
    """للأدمن — تفاصيل أكتر"""
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
    """الأدمن يضيف فني للخدمة"""
    provider_id = serializers.UUIDField()
 
    def validate_provider_id(self, value):
        from accounts.models import Provider
        try:
            provider = Provider.objects.get(id=value, is_approved=True, is_active=True)
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
            raise serializers.ValidationError(
                "thumbnail_url is required for videos."
            )
        return attrs

class ServiceCompletionFormSerializer(serializers.ModelSerializer):
    """للعرض — فني وأدمن"""
    media         = CompletionMediaSerializer(many=True, read_only=True)
    booking_id    = serializers.UUIDField(source='booking.id', read_only=True)
    previous_work = serializers.SerializerMethodField()

    class Meta:
        model  = ServiceCompletionForm
        fields = [
            'id', 'booking_id', 'notes',
            'is_finished', 'finished_at',
            'media', 'previous_work', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_previous_work(self, obj):
        try:
            return PreviousWorkSerializer(obj.previous_work).data
        except PreviousWork.DoesNotExist:
            return None


class ServiceCompletionFormUpdateSerializer(serializers.ModelSerializer):
    """الفني يضيف ملاحظات ويعمل finish"""
    class Meta:
        model  = ServiceCompletionForm
        fields = ['notes', 'is_finished']

    def validate(self, attrs):
        form = self.instance  # موجود دايماً لأنها PATCH
        if form.is_finished:
            raise serializers.ValidationError(
                "This completion form is already finished."
            )
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
    
# ==================== COUPON SERIALIZERS ====================

class CouponSerializer(serializers.ModelSerializer):
    """للعميل — بعد ما يتحقق من الكوبون"""
    class Meta:
        model  = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'max_discount', 'min_booking_cost', 'valid_until'
        ]
        read_only_fields = fields


class CouponAdminSerializer(serializers.ModelSerializer):
    """للأدمن — كل التفاصيل"""
    service_title = serializers.CharField(source='service.title', read_only=True)
    usage_left    = serializers.SerializerMethodField()

    def get_usage_left(self, obj):
        if obj.max_uses is None:
            return None   # غير محدود
        return max(0, obj.max_uses - obj.used_count)

    class Meta:
        model  = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'max_discount', 'min_booking_cost',
            'valid_from', 'valid_until',
            'max_uses', 'used_count', 'usage_left',
            'service', 'service_title',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'used_count', 'created_at', 'service_title', 'usage_left']


class CouponWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Coupon
        fields = [
            'code', 'discount_type', 'discount_value',
            'max_discount', 'min_booking_cost',
            'valid_from', 'valid_until',
            'max_uses', 'service', 'is_active'
        ]

    def validate_code(self, value):
        value = value.strip().upper()
        qs = Coupon.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("هذا الكود مستخدم بالفعل.")
        return value

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("قيمة الخصم يجب أن تكون أكبر من 0.")
        return value

    def validate(self, attrs):
        discount_type  = attrs.get('discount_type')
        discount_value = attrs.get('discount_value', 0)

        if discount_type == 'percentage' and discount_value > 100:
            raise serializers.ValidationError(
                "نسبة الخصم لا يمكن أن تتجاوز 100%."
            )
        if attrs.get('valid_from') and attrs.get('valid_until'):
            if attrs['valid_from'] >= attrs['valid_until']:
                raise serializers.ValidationError(
                    "تاريخ الانتهاء يجب أن يكون بعد تاريخ البداية."
                )
        return attrs


class CouponValidateSerializer(serializers.Serializer):
    """العميل يتحقق من كوبون قبل الحجز"""
    code       = serializers.CharField(max_length=50)
    service_id = serializers.UUIDField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, attrs):
        code = attrs['code'].strip().upper()
        service_id = attrs['service_id']
        total_cost = attrs['total_cost']

        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("الكوبون غير صحيح.")

        valid, error = coupon.is_valid()
        if not valid:
            raise serializers.ValidationError(error)

        # لو الكوبون مخصص لخدمة معينة
        if coupon.service and str(coupon.service.id) != str(service_id):
            raise serializers.ValidationError("هذا الكوبون غير صالح لهذه الخدمة.")

        # حد أدنى لقيمة الحجز
        if coupon.min_booking_cost and total_cost < coupon.min_booking_cost:
            raise serializers.ValidationError(
                f"الحد الأدنى لاستخدام هذا الكوبون هو "
                f"{coupon.min_booking_cost} ر.س."
            )

        attrs['coupon'] = coupon
        return attrs
    

class PreviousWorkSerializer(serializers.ModelSerializer):
    """للعميل — يشوف الأعمال السابقة"""
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
        return PreviousWork.objects.create(
            service=form.booking.service,
            completion_form=form,
            **validated_data
        )

class ProviderCompletionFormListItemSerializer(serializers.Serializer):
    attribute_id   = serializers.CharField(source='attribute.id')
    attribute_name = serializers.CharField(source='attribute.name')
    unit_name      = serializers.CharField(source='attribute.unit_name')
    quantity_name  = serializers.CharField(source='attribute.quantity_name')
    value          = serializers.DecimalField(max_digits=10, decimal_places=2)


class ProviderCompletionFormListSerializer(serializers.Serializer):
    id          = serializers.UUIDField()
    booking_id  = serializers.SerializerMethodField()
    service_title = serializers.SerializerMethodField()
    customer_address = serializers.SerializerMethodField()
    is_finished = serializers.BooleanField()
    finished_at = serializers.DateTimeField()
    created_at  = serializers.DateTimeField()
    items       = serializers.SerializerMethodField()

    def get_booking_id(self, obj):
        return str(obj.booking_id) if obj.booking_id else None

    def get_service_title(self, obj):
        if obj.booking and obj.booking.service:
            return obj.booking.service.title
        return None

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

    def get_items(self, obj):
        if not obj.booking:
            return []
        items = obj.booking.items.select_related('attribute').all()
        return ProviderCompletionFormListItemSerializer(items, many=True).data