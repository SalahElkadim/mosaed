from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from existedservices.models import ServiceCompletionForm
from .models import PaymentRequest


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
    من الـ ServiceOffer المقبول.

    existedservices (booking) برة النطاق ده تمامًا — مفيش أي تعامل
    مالي جوه التطبيق لخدماته الجاهزة.
    """
    old_is_finished = getattr(instance, '_old_is_finished', False)
    just_finished   = (not old_is_finished) and instance.is_finished

    if not just_finished:
        return

    custom_request = instance.custom_request
    if not custom_request:
        # ده completion form بتاع booking عادي — مش من اهتمامنا هنا
        return

    # already عندنا PaymentRequest؟ (get_or_create احتياطًا من أي تكرار signal)
    if hasattr(instance, 'payment_request'):
        return

    accepted_offer = custom_request.offers.filter(status='accepted').first()
    if not accepted_offer:
        # حالة غير متوقعة (الطلب اتعمله finish من غير عرض مقبول) — بنتجاهلها
        # بدل ما نكسر الـ save بتاع completion form
        return

    PaymentRequest.objects.get_or_create(
        completion_form=instance,
        defaults={
            'amount':         accepted_offer.final_price,
            'provider_share': accepted_offer.provider_price,
            'platform_share': accepted_offer.platform_fee,
        }
    )
