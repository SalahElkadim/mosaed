import uuid
from django.db import models
from accounts.models import Customer
from accounts.models import Specialization  # في الأعلى


# ==================== EXISTED SERVICE ====================

class ExistedService(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title    = models.CharField(max_length=255)
    image    = models.URLField(blank=True, null=True)
    details  = models.TextField()
    date     = models.DateField()
    visit_cost = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    specialization = models.ForeignKey(
        'accounts.Specialization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='services'
    )

    class Meta:
        db_table = 'existed_services'
        verbose_name = 'Existed Service'
        verbose_name_plural = 'Existed Services'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ==================== WARRANTY ====================

class Warranty(models.Model):

    DURATION_TYPE_CHOICES = [
        ('day',   'Day'),
        ('month', 'Month'),
        ('year',  'Year'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.OneToOneField(
        ExistedService,
        on_delete=models.CASCADE,
        related_name='warranty'
    )
    duration_value = models.PositiveIntegerField()
    duration_type  = models.CharField(
        max_length=10,
        choices=DURATION_TYPE_CHOICES,
        default='month'
    )
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'warranties'
        verbose_name = 'Warranty'
        verbose_name_plural = 'Warranties'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.service.title} — {self.duration_value} {self.duration_type}(s)"
# ==================== SERVICE ATTRIBUTE ====================

class ServiceAttribute(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        ExistedService,
        on_delete=models.CASCADE,
        related_name='attributes'
    )
    name      = models.CharField(max_length=255)   # عزل فوم / عزل مازوت
    details   = models.TextField(blank=True)        # تفاصيل خاصة بالـ attribute
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    # ← أضف الحقلين دول
    unit_name     = models.CharField(max_length=100, blank=True, default='')   # متر مربع
    quantity_name = models.CharField(max_length=100, blank=True, default='')   # المساحة
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service_attributes'
        verbose_name = 'Service Attribute'
        verbose_name_plural = 'Service Attributes'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} - {self.unit_cost}/unit ({self.service.title})"


# ==================== BOOKING ====================

class Booking(models.Model):

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    service  = models.ForeignKey(ExistedService, on_delete=models.CASCADE, related_name='bookings')
    provider = models.ForeignKey('accounts.Provider',on_delete=models.SET_NULL,null=True, blank=True,related_name='bookings')
    address = models.ForeignKey('accounts.CustomerAddress',on_delete=models.SET_NULL,null=True, blank=True,related_name='bookings')
    scheduled_date = models.DateField()
    notes          = models.TextField(blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # snapshot وقت الحجز - مش بيتغير حتى لو الـ unit_cost اتغير بعدين
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon = models.ForeignKey(
            'Coupon',
            on_delete=models.SET_NULL,
            null=True, blank=True,
            related_name='bookings'
        )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_cost      = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.customer} - {self.service.title} ({self.status})"

    def calculate_total(self):
        """بيحسب الـ total من الـ items ويخزنه"""
        total = sum(item.cost for item in self.items.all())
        self.total_cost = total
        self.save(update_fields=['total_cost'])
        return total


# ==================== BOOKING ITEM ====================

class BookingItem(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking   = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    attribute = models.ForeignKey(ServiceAttribute, on_delete=models.CASCADE, related_name='booking_items')

    value              = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    cost               = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'booking_items'
        verbose_name = 'Booking Item'
        verbose_name_plural = 'Booking Items'

    def save(self, *args, **kwargs):
        if not self.unit_cost_snapshot:
            self.unit_cost_snapshot = self.attribute.unit_cost
        self.cost = self.unit_cost_snapshot * self.value
        super().save(*args, **kwargs)
        # بعد ما الـ item اتحفظ، حدّث الـ total على الـ Booking
        self.booking.total_cost = sum(
            item.cost for item in self.booking.items.all()
        )
        self.booking.save(update_fields=['total_cost'])
    
    def delete(self, *args, **kwargs):
        booking = self.booking
        super().delete(*args, **kwargs)
        booking.total_cost = sum(item.cost for item in booking.items.all())
        booking.save(update_fields=['total_cost'])

    def __str__(self):
        return f"{self.attribute.name} × {self.value} = {self.cost}"
    
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
# from accounts.models import Customer  ← موجودة عندك بالفعل
# from .models import ExistedService    ← موجودة عندك بالفعل
 
 
class ServiceReview(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service  = models.ForeignKey(
        'ExistedService',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    customer = models.ForeignKey(
        'accounts.Customer',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    stars   = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'service_reviews'
        verbose_name = 'Service Review'
        verbose_name_plural = 'Service Reviews'
        ordering = ['-created_at']
        # كل customer يقدر يعمل review واحد بس لكل service
        unique_together = [('service', 'customer')]
 
    def __str__(self):
        return f"{self.customer} → {self.service.title} ({self.stars}★)"
    

class ServiceProvider(models.Model):
    """
    ربط فني (Provider) بخدمة (ExistedService).
    الأدمن هو اللي يعمل الربط ده.
    """
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service  = models.ForeignKey(
        'ExistedService',
        on_delete=models.CASCADE,
        related_name='service_providers'
    )
    provider = models.ForeignKey(
        'accounts.Provider',
        on_delete=models.CASCADE,
        related_name='service_assignments'
    )
    is_available = models.BooleanField(default=True)   # الأدمن يقدر يوقفه مؤقتاً
    created_at   = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = 'service_providers'
        verbose_name = 'Service Provider'
        verbose_name_plural = 'Service Providers'
        unique_together = [('service', 'provider')]    # مينفعش نفس الفني يتضاف مرتين لنفس الخدمة
        ordering = ['created_at']
 
    def __str__(self):
        return f"{self.provider.name} → {self.service.title}"
    

class ServiceCompletionForm(models.Model):

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('provider_arrived', 'Provider Arrived'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='completion_form'
    )
    custom_request = models.OneToOneField(
        'custom_services.CustomRequest',
        on_delete=models.CASCADE,
        related_name='completion_form',
        null=True, blank=True
    )
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')   # ← جديد
    started_at  = models.DateTimeField(null=True, blank=True)                                   # ← جديد
    notes       = models.TextField(blank=True)
    is_finished = models.BooleanField(default=False)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'service_completion_forms'
        verbose_name = 'Service Completion Form'
        ordering     = ['-created_at']

    def __str__(self):
        return f"CompletionForm for Booking#{self.booking.id} — finished={self.is_finished}"

class CompletionMedia(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        ServiceCompletionForm,
        on_delete=models.CASCADE,
        related_name='media'
    )
    media_type    = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    media_url     = models.URLField()
    thumbnail_url = models.URLField(blank=True, null=True)   # للفيديو بس
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'completion_media'
        verbose_name = 'Completion Media'
        ordering     = ['created_at']

    def __str__(self):
        return f"{self.media_type} — {self.form.booking.id}"
    
from django.utils import timezone

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),   # نسبة مئوية
        ('fixed',      'Fixed Amount'), # قيمة ثابتة
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code         = models.CharField(max_length=50, unique=True)
    discount_type  = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    # حد أقصى للخصم لو النوع percentage (اختياري)
    max_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # حد أدنى لقيمة الحجز عشان الكوبون يشتغل (اختياري)
    min_booking_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # صلاحية الكوبون
    valid_from   = models.DateTimeField()
    valid_until  = models.DateTimeField()

    # عدد مرات الاستخدام
    max_uses     = models.PositiveIntegerField(null=True, blank=True)  # None = غير محدود
    used_count   = models.PositiveIntegerField(default=0)

    # خاص بخدمة معينة أو للكل
    service = models.ForeignKey(
        ExistedService,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='coupons'
    )

    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'coupons'
        verbose_name = 'Coupon'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.code} — {self.discount_value}{'%' if self.discount_type == 'percentage' else ' ر.س'}"

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False, "الكوبون غير نشط."
        if now < self.valid_from:
            return False, "الكوبون لم يبدأ بعد."
        if now > self.valid_until:
            return False, "انتهت صلاحية الكوبون."
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False, "تم استنفاد عدد مرات استخدام الكوبون."
        return True, None

    def calc_discount(self, total_cost):
        """يحسب قيمة الخصم على الـ total"""
        if self.discount_type == 'percentage':
            discount = (self.discount_value / 100) * total_cost
            if self.max_discount:
                discount = min(discount, self.max_discount)
        else:
            discount = min(self.discount_value, total_cost)
        return round(discount, 2)
    

class PreviousWork(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        ExistedService,
        on_delete=models.CASCADE,
        related_name='previous_works'
    )
    completion_form = models.OneToOneField(
        ServiceCompletionForm,
        on_delete=models.CASCADE,
        related_name='previous_work',
        null=True, blank=True   # null لأنه بيتعمل بعد اتمام الخدمة
    )
    before_image = models.URLField(null=True, blank=True)
    after_image  = models.URLField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'service_previous_works'
        verbose_name = 'Previous Work'
        ordering     = ['-created_at']

    def __str__(self):
        return f"PreviousWork for {self.service.title} — form#{self.completion_form_id}"