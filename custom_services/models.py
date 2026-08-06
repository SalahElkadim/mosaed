import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


# ==================== PLATFORM SETTINGS ====================

class PlatformSettings(models.Model):
    """
    إعدادات عامة للمنصة — key/value store
    مثال: platform_fee_percentage = 20
    """
    key        = models.CharField(max_length=100, unique=True)
    value      = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'platform_settings'
        verbose_name = 'Platform Setting'

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_platform_fee(cls):
        """يرجع نسبة المنصة كـ Decimal — default 20"""
        from decimal import Decimal
        try:
            setting = cls.objects.get(key='platform_fee_percentage')
            return Decimal(setting.value)
        except cls.DoesNotExist:
            return Decimal('20')


# ==================== CUSTOM REQUEST ====================

class CustomRequest(models.Model):

    STATUS_CHOICES = [
        ('published',        'Published'),
        ('offers_received',  'Offers Received'),
        ('accepted',         'Accepted'),
        ('in_progress',      'In Progress'),
        ('completed',        'Completed'),
        ('cancelled',        'Cancelled'),
        ('expired',          'Expired'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer       = models.ForeignKey(
        'accounts.Customer',
        on_delete=models.CASCADE,
        related_name='custom_requests'
    )
    specialization = models.ForeignKey(
        'accounts.Specialization',
        on_delete=models.SET_NULL,
        null=True,
        related_name='custom_requests'
    )
    title          = models.CharField(max_length=255)
    description    = models.TextField()
    image          = models.URLField(null=True, blank=True)   # Cloudinary URL — اختياري

    address = models.ForeignKey(
        'accounts.CustomerAddress',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='custom_requests'
    )

    scheduled_date = models.DateField()
    status         = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='published'
    )

    # ينتهي تلقائياً بعد 24 ساعة من النشر
    expires_at = models.DateTimeField(null=True, blank=True)

    # الفني المقبول — بيتحدد لما العميل يقبل عرض
    accepted_provider = models.ForeignKey(
        'accounts.Provider',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='accepted_custom_requests'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'custom_requests'
        verbose_name = 'Custom Request'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.customer.name} — {self.title} ({self.status})"

    def save(self, *args, **kwargs):
        # بنحسب expires_at أول مرة بس
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def check_and_expire(self):
        """
        Lazy check — بنستدعيه لما الطلب يتجيب
        لو فات الوقت ومفيش قبول، نحوله expired
        """
        if (
            self.status in ('published', 'offers_received')
            and self.is_expired()
        ):
            self.status = 'expired'
            self.save(update_fields=['status'])
            return True
        return False


# ==================== SERVICE OFFER ====================

class ServiceOffer(models.Model):

    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('accepted',   'Accepted'),
        ('rejected',   'Rejected'),
        ('withdrawn',  'Withdrawn'),
    ]

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request  = models.ForeignKey(
        CustomRequest,
        on_delete=models.CASCADE,
        related_name='offers'
    )
    provider = models.ForeignKey(
        'accounts.Provider',
        on_delete=models.CASCADE,
        related_name='custom_offers'
    )

    provider_price = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    note   = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'service_offers'
        verbose_name = 'Service Offer'
        ordering     = ['created_at']
        # كل فني يقدر يعمل عرض واحد بس على نفس الطلب
        unique_together = [('request', 'provider')]

    def __str__(self):
        return f"{self.provider.name} → {self.request.title}: {self.final_price} ر.س"

    def save(self, *args, **kwargs):
        """بيحسب platform_fee و final_price تلقائياً"""
        fee_percentage  = PlatformSettings.get_platform_fee()
        self.platform_fee = round(self.provider_price * fee_percentage / 100, 2)
        self.final_price  = round(self.provider_price + self.platform_fee, 2)
        super().save(*args, **kwargs)


# ==================== REQUEST CHAT ====================

class RequestChat(models.Model):

    SENDER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('provider', 'Provider'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request     = models.ForeignKey(
        CustomRequest,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    sender_id   = models.UUIDField()    # ID العميل أو الفني
    message     = models.TextField()

    # جديد: حالة القراءة — بتتحدث لما الطرف المستقبل يفتح شاشة الشات
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'request_chats'
        verbose_name = 'Request Chat'
        ordering     = ['created_at']
        indexes = [
            models.Index(fields=['request', 'sender_type', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender_type}:{self.sender_id} → Request#{self.request.id}"

    @classmethod
    def mark_as_read_for_recipient(cls, custom_request, recipient_type):
        """
        بتعلّم كل الرسائل اللي بعتها 'الطرف التاني' (مش recipient_type) كمقروءة.
        مثال: لو العميل (recipient_type='customer') فتح الشات، بنعلّم رسائل الفني
        كمقروءة (لأن الفني هو اللي بعتها والعميل هو اللي قراها).

        بترجع الـ queryset اللي اتحدث (list of ids) عشان نقدر نبعتهم في إشعار الـ WebSocket.
        """
        sender_type_to_mark = 'provider' if recipient_type == 'customer' else 'customer'

        unread_messages = cls.objects.filter(
            request=custom_request,
            sender_type=sender_type_to_mark,
            is_read=False,
        )
        message_ids = list(unread_messages.values_list('id', flat=True))

        if message_ids:
            cls.objects.filter(id__in=message_ids).update(
                is_read=True,
                read_at=timezone.now(),
            )

        return message_ids

class Notification(models.Model):
    RECIPIENT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('provider', 'Provider'),
    ]
 
    EVENT_CHOICES = [
    ('new_custom_request', 'New Custom Request'),
    ('new_offer', 'New Offer'),
    ('offer_accepted', 'Offer Accepted'),
    ('new_chat_message', 'New Chat Message'),
    ('payment_received', 'Payment Received'),
    ('due_payment_required', 'Due Payment Required'),
    ('account_unblocked', 'Account Unblocked'),
    ('payment_required', 'Payment Required'),
    ('points_credited', 'Points Credited'),
]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
 
    # زي RequestChat بالظبط — مفيش FK واحد ينفع للعميل والفني مع بعض،
    # فبنستخدم CharField للـ id + حقل نوع منفصل
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPE_CHOICES)
    recipient_id = models.CharField(max_length=100)
 
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=255, blank=True)
 
    # أي بيانات إضافية (request_id, offer_id, distance_km...) عشان الفلاتر
    # يقدر يوجه اليوزر أو يستخدمها من غير ما نعمل حقول منفصلة لكل event
    data = models.JSONField(default=dict, blank=True)
 
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_type', 'recipient_id', 'is_read']),
        ]
 
    def __str__(self):
        return f"{self.recipient_type}:{self.recipient_id} - {self.event}"
 
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])



class DeviceToken(models.Model):
    """
    توكن FCM لجهاز واحد. اليوزر (عميل أو فني) ممكن يكون عنده أكتر من
    توكن في نفس الوقت (موبايل + تابلت مثلاً)، فمفيش unique على اليوزر
    نفسه، بس التوكن نفسه لازم يكون unique (توكن واحد بيمثل جهاز واحد).
    """
    RECIPIENT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('provider', 'Provider'),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
 
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPE_CHOICES)
    recipient_id = models.CharField(max_length=100)
 
    token = models.CharField(max_length=255, unique=True)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'device_tokens'
        indexes = [
            models.Index(fields=['recipient_type', 'recipient_id']),
        ]
 
    def __str__(self):
        return f"{self.recipient_type}:{self.recipient_id} — {self.token[:20]}..."
 