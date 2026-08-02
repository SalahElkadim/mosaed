import uuid
from django.db import models
from django.utils import timezone


# ====================================================================
# ملاحظة معمارية مهمة:
# نظام الدفع ده بيتطبق بس على custom_services (الطلبات المخصصة).
# existedservices (الحجوزات على الخدمات الجاهزة) برة النطاق ده تمامًا —
# بتتسوى مانوالي مع الفني من غير أي تعامل مالي جوه التطبيق.
#
# مفيش أي إعادة حساب لنسبة المنصة هنا وقت الدفع؛ القيم كلها snapshot
# من الـ ServiceOffer المقبول وقت ما اتعمل (provider_price/platform_fee/
# final_price)، فلو الأدمن غيّر PlatformSettings.platform_fee_percentage
# بعدين، الطلبات القديمة تفضل زي ما هي والجديد بس ياخد النسبة الجديدة.
# ====================================================================


# ==================== PAYMENT REQUEST ====================

class PaymentRequest(models.Model):
    """
    نموذج الدفع — بيتعمل تلقائيًا (عبر signal) لما الفني يعلّم
    ServiceCompletionForm بتاع custom_request كـ finished.
    """

    METHOD_CHOICES = [
        ('online', 'Online'),
        ('cash', 'Cash'),
    ]

    STATUS_CHOICES = [
        ('awaiting_method', 'Awaiting Method'),                # لسه العميل مختارش
        ('awaiting_gateway_payment', 'Awaiting Gateway Payment'),  # اختار أونلاين، مستني يدفع فعليًا
        ('awaiting_cash_confirmation', 'Awaiting Cash Confirmation'),  # اختار كاش، مستني الفني يأكد
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    completion_form = models.OneToOneField(
        'existedservices.ServiceCompletionForm',
        on_delete=models.CASCADE,
        related_name='payment_request'
    )

    # snapshot من الـ ServiceOffer المقبول وقت إنشاء نموذج الدفع
    amount         = models.DecimalField(max_digits=10, decimal_places=2)  # = final_price (اللي العميل بيدفعه)
    provider_share = models.DecimalField(max_digits=10, decimal_places=2)  # = provider_price
    platform_share = models.DecimalField(max_digits=10, decimal_places=2)  # = platform_fee
    points_used            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    marketing_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=10, choices=METHOD_CHOICES, null=True, blank=True
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='awaiting_method'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'payment_requests'
        verbose_name = 'Payment Request'
        ordering     = ['-created_at']

    def __str__(self):
        return f"PaymentRequest#{self.id} — {self.amount} ر.س ({self.status})"

    @property
    def custom_request(self):
        return self.completion_form.custom_request

    @property
    def provider(self):
        cr = self.custom_request
        return cr.accepted_provider if cr else None

    @property
    def customer(self):
        cr = self.custom_request
        return cr.customer if cr else None

    @property
    def customer_id(self):
        cr = self.custom_request
        return cr.customer_id if cr else None

    @property
    def provider_id(self):
        cr = self.custom_request
        return cr.accepted_provider_id if cr else None

    @property
    def final_amount(self):
        """المبلغ الفعلي المطلوب دفعه بعد خصم النقاط (لو اتستخدمت)"""
        return self.amount - self.points_discount_amount- self.marketing_discount_amount

    def mark_paid(self):
        if self.status != 'paid':
            self.status  = 'paid'
            self.paid_at = timezone.now()
            self.save(update_fields=['status', 'paid_at'])


# ==================== ONLINE PAYMENT ATTEMPT ====================

class OnlinePaymentAttempt(models.Model):
    """
    محاولة دفع أونلاين واحدة عبر ميسر. منفصلة عن PaymentRequest عشان
    لو العميل حاول ودفعه فشل، يقدر يعيد المحاولة (attempt جديد) من غير
    ما نلخبط سجل PaymentRequest نفسه.
    """

    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.CASCADE, related_name='online_attempts'
    )

    moyasar_payment_id = models.CharField(max_length=255, null=True, blank=True)
    payment_url         = models.URLField(null=True, blank=True)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')

    # بنخزن رد ميسر كامل (الـ webhook payload) عشان أي مراجعة أو دعم فني لاحقًا
    raw_callback_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'online_payment_attempts'
        verbose_name = 'Online Payment Attempt'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Attempt#{self.id} for {self.payment_request_id} ({self.status})"


# ==================== PROVIDER WALLET (الدفع الأونلاين) ====================

class ProviderWallet(models.Model):
    """
    محفظة الفني — بتتجمع فيها نسبته من كل طلب اتدفع أونلاين، وكل أسبوع
    (يوم ثابت لكل الفنيين) بتتحول للفني بنكيًا عبر PayoutBatch.
    """

    provider = models.OneToOneField(
        'accounts.Provider', on_delete=models.CASCADE, related_name='wallet'
    )

    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_out     = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'provider_wallets'
        verbose_name = 'Provider Wallet'

    def __str__(self):
        return f"Wallet({self.provider.name}) — {self.available_balance} ر.س"

    def credit(self, amount, payment_request=None):
        """إضافة نسبة الفني من طلب اتدفع أونلاين"""
        self.available_balance += amount
        self.total_earned      += amount
        self.save(update_fields=['available_balance', 'total_earned', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='commission_credit',
            payment_request=payment_request,
            balance_after=self.available_balance,
        )

    def debit_for_payout(self, amount, batch_item=None):
        """خصم الرصيد بعد التحويل البنكي الفعلي (يدوي حاليًا)"""
        self.available_balance -= amount
        self.total_paid_out    += amount
        self.save(update_fields=['available_balance', 'total_paid_out', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=self,
            amount=-amount,
            transaction_type='payout_debit',
            batch_item=batch_item,
            balance_after=self.available_balance,
        )


class WalletTransaction(models.Model):
    """سجل (ledger) كل حركة على محفظة الفني — للشفافية والمراجعة"""

    TYPE_CHOICES = [
        ('commission_credit', 'Commission Credit'),
        ('payout_debit', 'Payout Debit'),
        ('reversal', 'Reversal'),
    ]

    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(ProviderWallet, on_delete=models.CASCADE, related_name='transactions')

    amount = models.DecimalField(max_digits=12, decimal_places=2)  # موجب أو سالب
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions'
    )
    batch_item = models.ForeignKey(
        'PayoutBatchItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions'
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'wallet_transactions'
        verbose_name = 'Wallet Transaction'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type}: {self.amount} → balance={self.balance_after}"


# ==================== PROVIDER DUE (الدفع الكاش) ====================

class ProviderDue(models.Model):
    """
    مستحقات المنصة على الفني — بتتجمع من نسبة المنصة كل ما الفني يستلم
    فلوس كاش من عميل. لو outstanding_amount فضل من غير سداد بعد التحصيل
    الأسبوعي، الفني بيتقفل (is_blocked) لحد ما يدفع.
    """

    provider = models.OneToOneField(
        'accounts.Provider', on_delete=models.CASCADE, related_name='due'
    )

    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_charged       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid          = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_blocked  = models.BooleanField(default=False)
    blocked_at  = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'provider_dues'
        verbose_name = 'Provider Due'

    def __str__(self):
        return f"Due({self.provider.name}) — outstanding={self.outstanding_amount}"

    def charge(self, amount, payment_request=None):
        """إضافة مستحقات جديدة (نسبة المنصة) بعد ما الفني يأكد استلام كاش"""
        self.outstanding_amount += amount
        self.total_charged      += amount
        self.save(update_fields=['outstanding_amount', 'total_charged', 'updated_at'])

        DueTransaction.objects.create(
            due=self,
            amount=amount,
            transaction_type='charge',
            payment_request=payment_request,
            balance_after=self.outstanding_amount,
        )

    def pay(self, amount, payment_request=None, collection_item=None):
        """تسديد (كامل أو جزء) من المستحقات — بيتنادى بعد نجاح دفع رابط التحصيل"""
        self.outstanding_amount -= amount
        self.total_paid         += amount
        if self.outstanding_amount <= 0:
            self.outstanding_amount = 0
            self.is_blocked  = False
            self.blocked_at  = None
        self.save(update_fields=[
            'outstanding_amount', 'total_paid', 'is_blocked', 'blocked_at', 'updated_at'
        ])

        DueTransaction.objects.create(
            due=self,
            amount=-amount,
            transaction_type='payment',
            payment_request=payment_request,
            collection_item=collection_item,
            balance_after=self.outstanding_amount,
        )

    def block(self):
        if not self.is_blocked:
            self.is_blocked = True
            self.blocked_at = timezone.now()
            self.save(update_fields=['is_blocked', 'blocked_at', 'updated_at'])


class DueTransaction(models.Model):
    """سجل (ledger) كل حركة على مستحقات الفني"""

    TYPE_CHOICES = [
        ('charge', 'Charge'),
        ('payment', 'Payment'),
        ('reversal', 'Reversal'),
    ]

    id  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    due = models.ForeignKey(ProviderDue, on_delete=models.CASCADE, related_name='transactions')

    amount = models.DecimalField(max_digits=12, decimal_places=2)  # موجب (charge) أو سالب (payment)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='due_transactions'
    )
    collection_item = models.ForeignKey(
        'DueCollectionItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='due_transactions'
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'due_transactions'
        verbose_name = 'Due Transaction'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type}: {self.amount} → outstanding={self.balance_after}"


# ==================== البواتش الأسبوعية ====================

class PayoutBatch(models.Model):
    """تشغيلة تحويل المحافظ الأسبوعية — يوم ثابت لكل الفنيين"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    week_start = models.DateField()
    week_end   = models.DateField()
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'payout_batches'
        verbose_name = 'Payout Batch'
        ordering     = ['-week_start']

    def __str__(self):
        return f"PayoutBatch {self.week_start} → {self.week_end} ({self.status})"


class PayoutBatchItem(models.Model):
    """نصيب كل فني جوه تشغيلة التحويل — الأدمن يحول بنكيًا يدويًا ويأكد هنا"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('transferred', 'Transferred'),
        ('failed', 'Failed'),
    ]

    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(PayoutBatch, on_delete=models.CASCADE, related_name='items')
    provider = models.ForeignKey('accounts.Provider', on_delete=models.CASCADE, related_name='payout_items')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    transferred_at       = models.DateTimeField(null=True, blank=True)
    admin_reference_note = models.CharField(max_length=255, blank=True)  # رقم/ملاحظة التحويل البنكي

    class Meta:
        db_table     = 'payout_batch_items'
        verbose_name = 'Payout Batch Item'
        unique_together = [('batch', 'provider')]

    def __str__(self):
        return f"{self.provider.name} — {self.amount} ر.س ({self.status})"

    def mark_transferred(self, reference_note=''):
        self.status               = 'transferred'
        self.transferred_at       = timezone.now()
        self.admin_reference_note = reference_note
        self.save(update_fields=['status', 'transferred_at', 'admin_reference_note'])

        self.provider.wallet.debit_for_payout(self.amount, batch_item=self)


# ==================== تحصيل المستحقات الأسبوعي ====================

class DueCollectionBatch(models.Model):
    """تشغيلة تحصيل المستحقات الأسبوعية — نفس يوم PayoutBatch"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    week_start = models.DateField()
    week_end   = models.DateField()
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'due_collection_batches'
        verbose_name = 'Due Collection Batch'
        ordering     = ['-week_start']

    def __str__(self):
        return f"DueCollectionBatch {self.week_start} → {self.week_end} ({self.status})"


class DueCollectionItem(models.Model):
    """
    رابط تحصيل أسبوعي لكل فني عليه مستحقات. المبلغ تراكمي — بياخد
    outstanding_amount كامل بتاع الفني وقت إنشاء الـ batch (يشمل أي
    مستحقات قديمة متأخرة من أسابيع سابقة مادفعهاش).
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(DueCollectionBatch, on_delete=models.CASCADE, related_name='items')
    provider = models.ForeignKey('accounts.Provider', on_delete=models.CASCADE, related_name='due_collection_items')

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)

    payment_link        = models.URLField(null=True, blank=True)
    moyasar_payment_id  = models.CharField(max_length=255, null=True, blank=True)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'due_collection_items'
        verbose_name = 'Due Collection Item'
        unique_together = [('batch', 'provider')]

    def __str__(self):
        return f"{self.provider.name} — due {self.amount_due} ر.س ({self.status})"



class CustomerWallet(models.Model):
    """
    محفظة نقاط العميل — كل نقطة = 1 ريال. بتتزاد تلقائيًا بعد يوم من
    نجاح أي دفع أونلاين (5% من final_amount المدفوع فعليًا)، وبتُستخدم
    كخصم وقت إنشاء طلب جديد (بحد أقصى 50% من قيمة الطلب، ومقصورة على
    الدفع الأونلاين بس).

    الخصم وقت الاستخدام بيتسجل كمصروف تسويقي منفصل (PointsMarketingExpense)
    — مفيش أي تأثير على platform_share ولا على provider_share في
    PaymentRequest، الاتنين بيفضلوا زي ما هما بالكامل.
    """

    customer = models.OneToOneField(
        'accounts.Customer', on_delete=models.CASCADE, related_name='points_wallet'
    )

    points_balance          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_earned_points     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_redeemed_points   = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'customer_point_wallets'
        verbose_name = 'Customer Points Wallet'

    def __str__(self):
        return f"PointsWallet({self.customer.name}) — {self.points_balance} نقطة"

    def redeem(self, points, payment_request):
        """حجز نقاط كخصم وقت الدفع"""
        self.points_balance        -= points
        self.total_redeemed_points += points
        self.save(update_fields=['points_balance', 'total_redeemed_points', 'updated_at'])

        CustomerPointsTransaction.objects.create(
            wallet=self,
            points=-points,
            transaction_type='redeemed',
            payment_request=payment_request,
            balance_after=self.points_balance,
        )

    def refund(self, points, payment_request):
        """إرجاع نقاط اتحجزت (العميل غيّر رأيه أو ألغى الاستخدام قبل الدفع)"""
        self.points_balance        += points
        self.total_redeemed_points -= points
        self.save(update_fields=['points_balance', 'total_redeemed_points', 'updated_at'])

        CustomerPointsTransaction.objects.create(
            wallet=self,
            points=points,
            transaction_type='refunded',
            payment_request=payment_request,
            balance_after=self.points_balance,
        )

    def credit_earned(self, points, payment_request):
        """تحويل نقاط pending إلى رصيد فعلي قابل للاستخدام"""
        self.points_balance      += points
        self.total_earned_points += points
        self.save(update_fields=['points_balance', 'total_earned_points', 'updated_at'])
        return self.points_balance


class CustomerPointsTransaction(models.Model):
    """سجل (ledger) كل حركة على محفظة نقاط العميل"""

    TYPE_CHOICES = [
        ('earned_pending',  'Earned (Pending)'),   # اتحسبت بس لسه معلّقة (يوم الانتظار)
        ('earned_credited', 'Earned (Credited)'),  # اتضافت فعليًا للرصيد
        ('redeemed',        'Redeemed'),           # اتخصمت كاستخدام وقت الدفع
        ('refunded',        'Refunded'),           # رجعت بعد ما كانت متحجزة
    ]

    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name='transactions')

    points = models.DecimalField(max_digits=10, decimal_places=2)  # موجب (earned/refund) أو سالب (redeem)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='points_transactions'
    )

    # بيفضل None لحد ما transaction_type يتحول من earned_pending لـ earned_credited
    # (يعني الرصيد لسه معلّقة ومحسوبتش على points_balance)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'customer_points_transactions'
        verbose_name = 'Customer Points Transaction'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type}: {self.points} نقطة"


class PointsMarketingExpense(models.Model):
    """
    سجل مصاريف نظام نقاط الولاء — كل خصم بيتسجل هنا كمصروف تسويقي
    مستقل تمامًا عن platform_share. النصيب بتاع الفني والمنصة في
    PaymentRequest بيفضلوا زي ما هما بالكامل من غير أي تأثير، والفرق
    ده بيتوثق هنا كـ "المنصة دفعته من جيبها كتسويق".
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_request = models.OneToOneField(
        PaymentRequest, on_delete=models.CASCADE, related_name='marketing_expense'
    )
    amount     = models.DecimalField(max_digits=10, decimal_places=2)  # = points_discount_amount وقتها
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'points_marketing_expenses'
        verbose_name = 'Points Marketing Expense'
        ordering     = ['-created_at']

    def __str__(self):
        return f"مصروف تسويقي {self.amount} ر.س — {self.payment_request_id}"
    

