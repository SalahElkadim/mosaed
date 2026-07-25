"""
usage: python manage.py generate_weekly_batches
"""
import uuid as uuid_lib
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from payments.models import (
    ProviderWallet, PayoutBatch, PayoutBatchItem,
    ProviderDue, DueCollectionBatch, DueCollectionItem,
)
from payments.utils.notifications import notify_provider_due_payment_required


class Command(BaseCommand):
    help = 'ينشئ تشغيلة التحويلات الأسبوعية وتشغيلة تحصيل المستحقات الأسبوعية'

    def handle(self, *args, **options):
        today = timezone.now().date()
        week_start = today - timedelta(days=7)
        week_end = today

        self._generate_payout_batch(week_start, week_end)
        self._generate_due_collection_batch(week_start, week_end)

    @transaction.atomic
    def _generate_payout_batch(self, week_start, week_end):
        wallets = ProviderWallet.objects.filter(available_balance__gt=0).select_related('provider')
        if not wallets.exists():
            self.stdout.write('مفيش أرصدة فنيين تتحول الأسبوع ده.')
            return

        batch = PayoutBatch.objects.create(week_start=week_start, week_end=week_end)
        for wallet in wallets:
            PayoutBatchItem.objects.create(
                batch=batch,
                provider=wallet.provider,
                amount=wallet.available_balance,
            )

        self.stdout.write(self.style.SUCCESS(
            f'اتعمل Payout Batch #{batch.id} — {wallets.count()} فني.'
        ))

    def _generate_due_collection_batch(self, week_start, week_end):
        """
        ملحوظة: مفيش نداء لـ Moyasar هنا خالص. اللينك اللي بيتبعت للفني
        هو رابط صفحتنا احنا (React)، والدفع الفعلي بيحصل لما الفني يفتح
        الصفحة ويستخدم Moyasar widget مباشرة — نفس أسلوب PaymentPage
        بتاع العميل بالظبط. الـ moyasar_payment_id بيتسجل بعدين وقت
        الـ callback، مش هنا.
        """
        dues = ProviderDue.objects.filter(outstanding_amount__gt=0).select_related('provider')
        if not dues.exists():
            self.stdout.write('مفيش مستحقات تتحصل الأسبوع ده.')
            return

        batch = DueCollectionBatch.objects.create(week_start=week_start, week_end=week_end)
        created_count = 0

        for due in dues:
            # حماية من التكرار — لو الفني عنده بالفعل رابط دفع pending
            # (من تشغيل سابق أو تشغيل مكرر غلط)، متعملش له واحد جديد
            # فوقه، عشان منضاعفش outstanding_amount في due.pay() لاحقًا.
            already_pending = DueCollectionItem.objects.filter(
                provider=due.provider, status='pending'
            ).exists()
            if already_pending:
                self.stderr.write(
                    f'الفني {due.provider_id} عنده رابط دفع pending بالفعل — تم التخطي.'
                )
                continue

            item_id = uuid_lib.uuid4()
            payment_link = f"{self._frontend_base_url()}/due-collection/{item_id}"

            # لازم نمسك الـ object الراجع من create() في متغير عشان
            # نستخدمه بعدين في notify_provider_due_payment_required
            collection_item = DueCollectionItem.objects.create(
                id=item_id,
                batch=batch,
                provider=due.provider,
                amount_due=due.outstanding_amount,
                payment_link=payment_link,
            )

            # القفل الفوري — زي ما اتفقنا، مفيش مهلة سماح دلوقتي
            due.block()
            created_count += 1

            notify_provider_due_payment_required(due.provider_id, collection_item)

        self.stdout.write(self.style.SUCCESS(
            f'اتعمل Due Collection Batch #{batch.id} — {created_count} فني اتقفلوا وبعتلهم روابط.'
        ))

    def _frontend_base_url(self):
        return getattr(settings, 'FRONTEND_URL', '').rstrip('/')