from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction

from existedservices.models import ServiceCompletionForm
from .models import PaymentRequest,CustomerWallet, CustomerPointsTransaction
from .utils.notifications import notify_customer_payment_required


@receiver(pre_save, sender=ServiceCompletionForm)
def _cache_old_finished_state(sender, instance, **kwargs):
    """
    بنخزن حالة is_finished القديمة قبل الحفظ، عشان نتأكد وقت الـ
    post_save إن التحديث ده فعلاً أول مرة يتحول فيها لـ True
    (نفس نمط _cache_old_offer_status في custom_services/signals.py)
    """
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
    لما نموذج الإتمام يتحول لـ is_finished=True، ولو ده طلب مخصص
    (custom_request مش None)، اعمل PaymentRequest تلقائيًا مع snapshot
    من الـ ServiceOffer المقبول، وبعت إشعار للعميل إن وقت الدفع جه.

    existedservices (booking) برة النطاق ده تمامًا — مفيش أي تعامل
    مالي جوه التطبيق لخدماته الجاهزة.
    """
    old_is_finished = getattr(instance, '_old_is_finished', False)
    just_finished   = (not old_is_finished) and instance.is_finished

    if not just_finished:
        return

    custom_request = instance.custom_request
    if not custom_request:
        return

    if hasattr(instance, 'payment_request'):
        return

    accepted_offer = custom_request.offers.filter(status='accepted').first()
    if not accepted_offer:
        return

    payment_request, was_created = PaymentRequest.objects.get_or_create(
        completion_form=instance,
        defaults={
            'amount':         accepted_offer.final_price,
            'provider_share': accepted_offer.provider_price,
            'platform_share': accepted_offer.platform_fee,
        }
    )

    if was_created:
        # transaction.on_commit مش لازمة هنا فعليًا لأن _create_and_send
        # نفسها بتستخدم on_commit جواها، بس مفيش ضرر من تركها كطبقة أمان
        # إضافية لو حصل تعديل مستقبلي في _create_and_send
        transaction.on_commit(
            lambda: notify_customer_payment_required(
                custom_request.customer_id,
                custom_request
            )
        )

from .tasks import credit_customer_points_task, POINTS_EARN_PERCENTAGE, POINTS_CREDIT_DELAY_SECONDS


def schedule_points_for_payment(payment_request):
    """
    بتتنادى مرة واحدة يدويًا بعد ما الدفع الأونلاين ينجح فعليًا (من
    _finalize_online_payment في views.py — مش post_save signal عادي،
    عشان نضمن إنها بتتنفذ بس عند النجاح الفعلي مش أي save).

    بتحسب النقاط على final_amount (المبلغ المدفوع فعليًا بعد أي خصم
    نقاط سابق، مش المبلغ الأصلي) — عشان العميل ميكسبش نقاط على الجزء
    اللي دفعه بنقاط أصلاً.
    """
    if payment_request.payment_method != 'online':
        return  # النقاط على الأونلاين بس

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
        balance_after=None,  # لسه معلّقة، مش محسوبة على الرصيد
    )

    # الجدولة بتحصل بعد commit الـ transaction الحالية عشان نضمن إن
    # CustomerPointsTransaction فعلاً اتسجلت في الداتابيز قبل ما
    # الـ Celery worker يحاول يقراها
    transaction.on_commit(
        lambda: credit_customer_points_task.apply_async(
            args=[txn.id], countdown=POINTS_CREDIT_DELAY_SECONDS
        )
    )