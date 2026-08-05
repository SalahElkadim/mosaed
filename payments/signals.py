from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from accounts.models import MarketingCode, MarketingCodeUsage  # يضاف مع الاستيراد
from existedservices.models import ServiceCompletionForm
from .models import PaymentRequest, CustomerWallet, CustomerPointsTransaction
from custom_services.models import  PlatformSettings
from .utils.notifications import notify_customer_payment_required
from decimal import Decimal, ROUND_HALF_UP


EXISTED_SERVICES_COMMISSION_KEY = 'existed_services_commission'
DEFAULT_EXISTED_SERVICES_COMMISSION_PERCENTAGE = Decimal('20')  # fallback لو الإعداد مش موجود لسه


def _get_existed_services_commission_percentage():
    """
    بيرجع نسبة عمولة المنصة على الخدمات الجاهزة (existedservices) من
    PlatformSettings. لو الإعداد مش موجود، بيتعمل بقيمة افتراضية 20%
    عشان النظام يفضل شغال حتى لو الأدمن لسه محددهاش يدويًا.
    """
    setting, created = PlatformSettings.objects.get_or_create(
        key=EXISTED_SERVICES_COMMISSION_KEY,
        defaults={'value': str(DEFAULT_EXISTED_SERVICES_COMMISSION_PERCENTAGE)}
    )
    try:
        return Decimal(str(setting.value))
    except (TypeError, ValueError, ArithmeticError):
        return DEFAULT_EXISTED_SERVICES_COMMISSION_PERCENTAGE


@receiver(pre_save, sender=ServiceCompletionForm)
def _cache_old_finished_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = ServiceCompletionForm.objects.get(pk=instance.pk)
            instance._old_is_finished = old.is_finished
        except ServiceCompletionForm.DoesNotExist:
            instance._old_is_finished = False
    else:
        instance._old_is_finished = False


@receiver(post_save, sender=ServiceCompletionForm)
def create_payment_request_on_finish(sender, instance, created, **kwargs):
    """
    لما نموذج الإتمام يخلص (is_finished=True لأول مرة)، اعمل
    PaymentRequest تلقائيًا — سواء كان الفورم مربوط بطلب مخصص
    (custom_request) أو بحجز خدمة جاهزة (booking).
    """
    old_is_finished = getattr(instance, '_old_is_finished', False)
    just_finished   = (not old_is_finished) and instance.is_finished

    if not just_finished:
        return

    if hasattr(instance, 'payment_request'):
        return

    custom_request = instance.custom_request
    booking        = instance.booking

    if custom_request:
        accepted_offer = custom_request.offers.filter(status='accepted').first()
        if not accepted_offer:
            return

        amount         = accepted_offer.final_price
        provider_share = accepted_offer.provider_price
        platform_share = accepted_offer.platform_fee
        customer_id    = custom_request.customer_id

    elif booking:
        visit_cost = booking.service.visit_cost or Decimal('0')
        amount = (booking.price or Decimal('0')) + visit_cost
        if amount <= 0:
            return

        commission_percentage = _get_existed_services_commission_percentage()
        platform_share = (amount * commission_percentage / Decimal('100')).quantize(Decimal('0.01'))
        provider_share = amount - platform_share
        customer_id = booking.customer_id

    else:
        # الفورم مش مربوط بأي طلب/حجز فعلي (حالة نادرة/دفاعية) — متعملش دفع
        return

    payment_request, was_created = PaymentRequest.objects.get_or_create(
        completion_form=instance,
        defaults={
            'amount':         amount,
            'provider_share': provider_share,
            'platform_share': platform_share,
        })

    if was_created:
        if custom_request:  # ماركتنج كود مقصور على custom_request بس
            _apply_marketing_code_discount(payment_request, custom_request.customer)

        transaction.on_commit(
            lambda: notify_customer_payment_required(customer_id, payment_request))


from .tasks import credit_customer_points_task, POINTS_EARN_PERCENTAGE, POINTS_CREDIT_DELAY_SECONDS


def schedule_points_for_payment(payment_request):
    """
    النقاط بتتحسب على الطلبات المخصصة بس. الخدمات الجاهزة (booking)
    مستبعدة تمامًا من نظام نقاط الولاء.
    """
    if payment_request.payment_method != 'online':
        return

    if not payment_request.completion_form.custom_request_id:
        return  # ← خط الدفاع: مفيش نقاط على existed services خالص

    customer = payment_request.customer
    if not customer:
        return

    points = round(payment_request.final_amount * POINTS_EARN_PERCENTAGE, 2)
    if points <= 0:
        return

    wallet, _ = CustomerWallet.objects.get_or_create(customer=customer)

    txn = CustomerPointsTransaction.objects.create(
        wallet=wallet,
        points=points,
        transaction_type='earned_pending',
        payment_request=payment_request,
        balance_after=None,
    )

    transaction.on_commit(
        lambda: credit_customer_points_task.apply_async(
            args=[txn.id], countdown=POINTS_CREDIT_DELAY_SECONDS
        )
    )

def _apply_marketing_code_discount(payment_request, customer):
    """
    لو ده أول custom request للعميل، وعنده signup_marketing_code لسه
    مستخدمش، يتطبق الخصم ويتسجل في MarketingCodeUsage.
    """
    if not customer or customer.marketing_discount_used:
        return

    code = customer.signup_marketing_code
    if not code or not code.is_active:
        return

    # هل ده أول payment_request خاص بطلبات custom request للعميل ده؟
    already_has_other = PaymentRequest.objects.filter(
        completion_form__custom_request__customer_id=customer.id
    ).exclude(pk=payment_request.pk).exists()

    if already_has_other:
        return

    discount = (payment_request.amount * code.discount_percentage / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    discount = min(discount, payment_request.amount)  # حماية دفاعية — الخصم مايتعداش المبلغ

    payment_request.marketing_discount_amount = discount
    payment_request.save(update_fields=['marketing_discount_amount'])

    MarketingCodeUsage.objects.create(
        marketing_code=code,
        customer=customer,
        payment_request=payment_request,
        discount_amount=discount,
    )

    customer.marketing_discount_used = True
    customer.save(update_fields=['marketing_discount_used'])
