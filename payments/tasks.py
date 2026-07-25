from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task(name='generate_weekly_batches')
def generate_weekly_batches_task():
    """
    بتنادي نفس management command الموجود (generate_weekly_batches) بدل
    ما نكرر المنطق هنا — مصدر واحد للحقيقة، ولو حد شغّلها يدوي من
    الترمينال هتفضل شغالة بنفس الطريقة بالظبط.
    """
    logger.info('[Celery] بدء تشغيل generate_weekly_batches')
    try:
        call_command('generate_weekly_batches')
        logger.info('[Celery] انتهى تشغيل generate_weekly_batches بنجاح')
    except Exception:
        # بنسجل الخطأ كامل بدل ما نسيبه يضيع في الـ worker logs من غير تتبع
        logger.exception('[Celery] فشل تشغيل generate_weekly_batches')
        raise