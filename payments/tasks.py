from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

POINTS_EARN_PERCENTAGE = 0.05  # 5%
POINTS_CREDIT_DELAY_SECONDS = 60 * 60 * 24  # يوم واحد


@shared_task(name='credit_customer_points')
def credit_customer_points_task(transaction_id):
    """
    بتتشغل بعد يوم بالظبط من وقت نجاح الدفع (عبر countdown وقت الجدولة).
    بتحوّل transaction من earned_pending لـ earned_credited وتضيف
    النقاط فعليًا لرصيد العميل، وتبعتله إشعار.

    idempotent: لو الـ transaction اتحول بالفعل (مثلاً لو اتنادت مرتين
    بالغلط)، بتتجاهل من غير ما تكرر الإضافة.
    """
    from .models import CustomerPointsTransaction
    from .utils.notifications import notify_customer_points_credited

    try:
        txn = CustomerPointsTransaction.objects.select_related('wallet').get(
            id=transaction_id, transaction_type='earned_pending'
        )
    except CustomerPointsTransaction.DoesNotExist:
        logger.info(f'[Celery] points transaction {transaction_id} already credited أو مش موجودة — تم التجاهل')
        return

    wallet = txn.wallet
    new_balance = wallet.credit_earned(txn.points, txn.payment_request)

    txn.transaction_type = 'earned_credited'
    txn.balance_after     = new_balance
    txn.save(update_fields=['transaction_type', 'balance_after'])

    notify_customer_points_credited(wallet.customer_id, txn)

    logger.info(f'[Celery] تم اعتماد {txn.points} نقطة لمحفظة العميل {wallet.customer_id}')