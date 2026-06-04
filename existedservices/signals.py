from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Booking, ServiceCompletionForm


@receiver(pre_save, sender=Booking)
def create_completion_form_on_complete(sender, instance, **kwargs):
    """
    لما الـ booking status يتحول لـ completed،
    اعمل ServiceCompletionForm تلقائياً لو مش موجود.
    """
    if not instance.pk:
        return  # booking جديد — مش هنتعامل معاه

    try:
        old = Booking.objects.get(pk=instance.pk)
    except Booking.DoesNotExist:
        return

    just_completed = (
        old.status != 'completed' and instance.status == 'completed'
    )

    if just_completed:
        # بنستخدم get_or_create عشان نضمن مفيش تكرار
        ServiceCompletionForm.objects.get_or_create(booking=instance)