from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task(name='expire_custom_requests')
def expire_custom_requests():
    from .models import CustomRequest

    expired = CustomRequest.objects.filter(
        status__in=['published', 'offers_received'],
        expires_at__lt=timezone.now()
    )

    count = expired.count()

    if count > 0:
        expired.update(status='expired')
        logger.info(f'[Celery] تم تحويل {count} طلب إلى expired')
    else:
        logger.info('[Celery] مفيش طلبات منتهية دلوقتي')

    return count