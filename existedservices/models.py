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
    name    = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service_attributes'
        verbose_name = 'Service Attribute'
        verbose_name_plural = 'Service Attributes'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} ({self.service.title})"
# ==================== BOOKING ====================

class Booking(models.Model):

    STATUS_CHOICES = [
        ('pending',         'Pending'),          # اتحجز، لسه مفيش تواصل
        ('awaiting_price',  'Awaiting Price'),    # الدعم بيتواصل مع العميل والفني
        ('price_proposed',  'Price Proposed'),    # السعر اتحط، مستني موافقة العميل
        ('confirmed',       'Confirmed'),         # العميل وافق
        ('completed',       'Completed'),
        ('cancelled',       'Cancelled'),
    ]

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    service  = models.ForeignKey(ExistedService, on_delete=models.CASCADE, related_name='bookings')
    provider = models.ForeignKey('accounts.Provider', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    address  = models.ForeignKey('accounts.CustomerAddress', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    scheduled_date = models.DateField()
    notes          = models.TextField(blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # السعر بيتحدد يدوياً من الأدمن بعد التواصل مع الفني
    price      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    priced_at  = models.DateTimeField(null=True, blank=True)   # وقت ما الأدمن حط السعر

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.customer} - {self.service.title} ({self.status})"

# ==================== BOOKING ITEM ====================

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
        null=True, blank=True,
        on_delete=models.SET_NULL,
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
        if self.booking:
            return f"CompletionForm for Booking#{self.booking.id} — finished={self.is_finished}"
        if self.custom_request:
            return f"CompletionForm for CustomRequest#{self.custom_request.id} — finished={self.is_finished}"
        return f"CompletionForm#{self.id} — finished={self.is_finished}"

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
    

class PreviousWork(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        ExistedService,
        null=True,
    blank=True,
    on_delete=models.SET_NULL,
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
        service_title = self.service.title if self.service else "خدمة محذوفة"
        return f"PreviousWork for {service_title} — form#{self.completion_form_id}"