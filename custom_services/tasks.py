from celery import shared_task
from django.utils import timezone
import logging
from datetime import timedelta

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

NOTIFICATION_READ_RETENTION_DAYS = 30      # المقروءة: تتحذف بعد 30 يوم
NOTIFICATION_UNREAD_RETENTION_DAYS = 90    # الغير مقروءة: تتحذف بعد 90 يوم (حتى لو محدش شافها)
 
 
@shared_task
def cleanup_old_notifications():
    """
    مهمة دورية (شغّلها يوميًا مرة عن طريق Celery Beat) بتحذف:
    - الإشعارات المقروءة الأقدم من NOTIFICATION_READ_RETENTION_DAYS
    - الإشعارات الغير مقروءة الأقدم من NOTIFICATION_UNREAD_RETENTION_DAYS
      (عشان الإشعار اللي محدش شافه من 3 شهور غالبًا بقى غير مهم أصلاً،
      ومنمنعش الجدول من إنه يكبر إلى ما لا نهاية لو يوزر مسيبش يفتح التطبيق)
 
    بترجع dict فيه عدد الصفوف المحذوفة من كل نوع، مفيد يظهر في الـ logs.
    """
    from .models import Notification
 
    now = timezone.now()
 
    read_cutoff = now - timedelta(days=NOTIFICATION_READ_RETENTION_DAYS)
    unread_cutoff = now - timedelta(days=NOTIFICATION_UNREAD_RETENTION_DAYS)
 
    read_deleted_count, _ = Notification.objects.filter(
        is_read=True,
        created_at__lt=read_cutoff,
    ).delete()
 
    unread_deleted_count, _ = Notification.objects.filter(
        is_read=False,
        created_at__lt=unread_cutoff,
    ).delete()
 
    result = {
        'read_deleted': read_deleted_count,
        'unread_deleted': unread_deleted_count,
        'ran_at': now.isoformat(),
    }
    return result