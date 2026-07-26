import logging

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser

from accounts.permissions import IsCustomer, IsProvider

from .models import (
    PaymentRequest, OnlinePaymentAttempt, ProviderWallet, WalletTransaction,
    ProviderDue, PayoutBatch, PayoutBatchItem, DueCollectionBatch, DueCollectionItem,
)
from .serializers import (
    PaymentRequestSerializer,
    PaymentMethodSelectSerializer,
    OnlinePaymentAttemptSerializer,
    InitiateOnlinePaymentSerializer,
    ProviderDuesStatusSerializer,
    ProviderWalletSerializer,
    WalletTransactionSerializer,
    PayoutBatchAdminSerializer,
    DueCollectionBatchAdminSerializer,DueTransactionSerializer,
)
from .utils.moyasar import create_payment_link, get_payment, verify_webhook_payload
from .utils.notifications import (
    notify_provider_payment_received,
    notify_provider_account_unblocked,
)
logger = logging.getLogger(__name__)


# ==================== عرض نموذج الدفع ====================

class PaymentRequestDetailView(APIView):
    """
    GET /payments/<payment_request_id>/
    العميل أو الفني المرتبط بالطلب يشوفوا تفاصيل نموذج الدفع.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type == 'customer' and pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)
        if user_type == 'provider' and pr.provider_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)


# ==================== اختيار طريقة الدفع ====================
class PaymentMethodSelectView(APIView):
    """
    POST /payments/<payment_request_id>/select-method/
    body: {"payment_method": "online" | "cash"}
    """
    permission_classes = [IsCustomer]

    def post(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentMethodSelectSerializer(
            data=request.data, context={'payment_request': pr}
        )
        serializer.is_valid(raise_exception=True)
        method = serializer.validated_data['payment_method']

        # النقاط شغالة على الأونلاين بس — لو العميل مستخدم نقاط
        # ومحاول يختار كاش، لازم يلغي النقاط الأول
        if method == 'cash' and pr.points_used > 0:
            return Response(
                {'error': 'لا يمكن الدفع كاش عند استخدام نقاط الولاء. يرجى إلغاء النقاط أولاً أو الدفع أونلاين.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pr.payment_method = method
        pr.status = 'awaiting_cash_confirmation' if method == 'cash' else 'awaiting_gateway_payment'
        pr.save(update_fields=['payment_method', 'status'])

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)
# ==================== تنفيذ الدفع الأونلاين بالـ token ====================

class InitiateOnlinePaymentView(APIView):
    """
    POST /payments/<payment_request_id>/initiate-online/
    body: {"token": "tok_xxx"}

    الفرونت بيعرض فورم Moyasar.js (زي StepPaymentPage.jsx بالظبط)، وبعد
    ما العميل يدخل بيانات الكارت، Moyasar.js بيولّد token في المتصفح
    ويبعته هنا. هنا بس بننادي Moyasar API فعليًا بالـ token ده.

    لو الدفع اتأكد فورًا (بدون 3DS) بنقفل العملية على طول. لو محتاج 3DS
    بنرجع transaction_url عشان الفرونت يعمل redirect عليه (والتأكيد
    النهائي بيحصل عبر PaymentRequestCallbackView أو الـ webhook).
    """
    permission_classes = [IsCustomer]

    def post(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        if pr.payment_method != 'online' or pr.status != 'awaiting_gateway_payment':
            return Response(
                {'error': 'لا يمكن تنفيذ الدفع في هذه المرحلة.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = InitiateOnlinePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        callback_url = f"{settings.FRONTEND_URL}/payments/{pr.id}/callback"

        try:
            payment_data = create_payment_link(
                amount_halalas=int(pr.amount * 100),
                description=f"دفع طلب خدمة #{pr.custom_request_id}",
                callback_url=callback_url,
                token=token,
                metadata={'payment_request_id': str(pr.id)},
            )
        except Exception as e:
            return Response(
                {'error': 'تعذر إنشاء طلب الدفع، حاول مرة أخرى.'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        moyasar_id      = payment_data.get('id')
        payment_status  = payment_data.get('status')
        transaction_url = payment_data.get('source', {}).get('transaction_url')

        attempt = OnlinePaymentAttempt.objects.create(
            payment_request=pr,
            moyasar_payment_id=moyasar_id,
            payment_url=transaction_url,
            raw_callback_data=payment_data,
        )

        if payment_status == 'paid':
            attempt.status = 'paid'
            attempt.save(update_fields=['status'])
            _finalize_online_payment(pr)
        elif payment_status == 'failed':
            attempt.status = 'failed'
            attempt.save(update_fields=['status'])

        return Response(
            {
                'payment_id': moyasar_id,
                'status': payment_status,
                'transaction_url': transaction_url,
                'payment_request': PaymentRequestSerializer(pr).data,
            },
            status=status.HTTP_200_OK
        )


# ==================== Callback بعد 3D Secure (نموذج الدفع الأساسي) ====================

class PaymentRequestCallbackView(APIView):
    """
    GET/POST /payments/<payment_request_id>/callback/
    Moyasar بيعمل redirect للفرونت بعد الـ 3DS على الرابط اللي بعتناه في
    callback_url، وصفحة الكولباك في الفرونت (زي StepPaymentCallback.jsx)
    بتنادي الـ endpoint ده بالـ JWT بتاع العميل مع الـ payment id.
    """
    permission_classes = [IsCustomer]

    def _handle(self, request, payment_request_id):
        payment_id = request.data.get('id') or request.query_params.get('id')
        if not payment_id:
            return Response({'error': 'payment_id مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pr = PaymentRequest.objects.get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            payment_data = get_payment(payment_id)
        except Exception:
            return Response({'error': 'تعذر التحقق من الدفع.'}, status=status.HTTP_502_BAD_GATEWAY)

        payment_status = payment_data.get('status')

        attempt = OnlinePaymentAttempt.objects.filter(moyasar_payment_id=payment_id).first()
        if attempt:
            attempt.raw_callback_data = payment_data
            attempt.status = 'paid' if payment_status == 'paid' else (
                'failed' if payment_status != 'initiated' else attempt.status
            )
            attempt.save(update_fields=['status', 'raw_callback_data', 'updated_at'])

        if payment_status == 'paid' and pr.status != 'paid':
            _finalize_online_payment(pr)

        return Response(
            {'status': payment_status, 'payment_request': PaymentRequestSerializer(pr).data},
            status=status.HTTP_200_OK
        )

    def get(self, request, payment_request_id):
        return self._handle(request, payment_request_id)

    def post(self, request, payment_request_id):
        return self._handle(request, payment_request_id)


from .signals import schedule_points_for_payment  # يضاف مع الـ imports فوق
from .models import PointsMarketingExpense          # يضاف مع الـ imports فوق


@transaction.atomic
def _finalize_online_payment(pr):
    pr = PaymentRequest.objects.select_for_update().get(pk=pr.pk)

    if pr.status == 'paid':
        return

    pr.mark_paid()
    wallet, _ = ProviderWallet.objects.get_or_create(provider=pr.provider)
    wallet.credit(pr.provider_share, payment_request=pr)  # نصيب الفني كامل، من غير أي تأثير بالخصم

    # تسجيل الخصم (لو موجود) كمصروف تسويقي منفصل تمامًا — مفيش أي
    # لمس لـ platform_share أو provider_share هنا خالص
    if pr.points_discount_amount > 0:
        PointsMarketingExpense.objects.create(
            payment_request=pr,
            amount=pr.points_discount_amount,
        )

    transaction.on_commit(lambda: notify_provider_payment_received(pr.provider_id, pr))
    schedule_points_for_payment(pr)

# ==================== Webhook ميسر ====================

class MoyasarWebhookView(APIView):
    """
    POST /payments/webhooks/moyasar/
    مفيش تحقق من هوية المستخدم هنا (ميسر مش عندها JWT بتاعنا) — بدل
    كده بنتحقق من صحة الطلب عبر verify_webhook_payload.

    الـ endpoint ده واحد بس لكل أنواع الدفع (moyasar_payment_id فريد
    عالميًا)، وبيفرّق بنفسه هل ده:
    1) دفع أونلاين لنموذج دفع أساسي (OnlinePaymentAttempt)
    2) تسديد مستحقات أسبوعية (DueCollectionItem)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if not verify_webhook_payload(request):
            return Response({'error': 'توقيع غير صالح.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        moyasar_id      = data.get('id') or data.get('data', {}).get('id')
        payment_status  = data.get('status') or data.get('data', {}).get('status')
        metadata        = data.get('metadata') or data.get('data', {}).get('metadata') or {}

        attempt = OnlinePaymentAttempt.objects.select_related('payment_request').filter(
            moyasar_payment_id=moyasar_id
        ).first()
        if attempt:
            return self._handle_online_payment(attempt, data, payment_status)

        # الأول بـ moyasar_payment_id (بعد ما الـ callback يكون سجّله)
        collection_item = DueCollectionItem.objects.select_related('provider').filter(
            moyasar_payment_id=moyasar_id
        ).first()

        # fallback — لو الـ webhook وصل قبل الـ callback، مفيش moyasar_payment_id
        # متسجل لسه، فبندور بـ metadata اللي بعتناها في Moyasar.init() نفسه
        if not collection_item:
            item_id = metadata.get('due_collection_item_id')
            if item_id:
                collection_item = DueCollectionItem.objects.select_related('provider').filter(
                    id=item_id, status='pending'
                ).first()
                if collection_item and not collection_item.moyasar_payment_id:
                    collection_item.moyasar_payment_id = moyasar_id
                    collection_item.save(update_fields=['moyasar_payment_id'])

        if collection_item:
            return self._handle_due_collection(collection_item, payment_status)

        return Response({'error': 'عملية الدفع غير معروفة.'}, status=status.HTTP_404_NOT_FOUND)

    def _handle_online_payment(self, attempt, data, payment_status):
        attempt.raw_callback_data = data
        pr = attempt.payment_request

        if payment_status == 'paid':
            attempt.status = 'paid'
            attempt.save(update_fields=['status', 'raw_callback_data', 'updated_at'])

            # بدل تكرار منطق mark_paid + wallet.credit هنا، بننادي نفس
            # الدالة المستخدمة في الـ callback — مصدر واحد للمنطق، وبالتبعية
            # نفس حماية select_for_update ضد التكرار
            _finalize_online_payment(pr)
        else:
            attempt.status = 'failed'
            attempt.save(update_fields=['status', 'raw_callback_data', 'updated_at'])

        return Response({'message': 'تم الاستلام.'}, status=status.HTTP_200_OK)

    def _handle_due_collection(self, collection_item, payment_status):
        if payment_status == 'paid':
            _finalize_due_payment(collection_item)
        else:
            collection_item.status = 'failed'
            collection_item.save(update_fields=['status'])

        return Response({'message': 'تم الاستلام.'}, status=status.HTTP_200_OK)


# ==================== تأكيد الفني لاستلام الكاش ====================
class ConfirmCashPaymentView(APIView):
    """
    POST /payments/<payment_request_id>/confirm-cash/
    الفني يأكد إنه استلم الفلوس كاش من العميل فعليًا.
    """
    permission_classes = [IsProvider]

    def post(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.provider_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        if pr.payment_method != 'cash' or pr.status != 'awaiting_cash_confirmation':
            return Response(
                {'error': 'لا يمكن تأكيد الدفع في هذه الحالة.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pr.mark_paid()

        due, _ = ProviderDue.objects.get_or_create(provider=pr.provider)
        # نصيب المنصة كامل من غير خصم — النقاط ممنوعة أصلاً مع الكاش
        # (راجع التحقق في PaymentMethodSelectView تحت)، فالسطر ده
        # طبقة حماية إضافية بس (defensive)
        due.charge(pr.platform_share, payment_request=pr)

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)
# ==================== حالة مستحقات الفني (مستثناة من القفل) ====================

class ProviderDuesStatusView(APIView):
    """
    GET /provider/dues/status/
    هذا الـ endpoint وحده (+ endpoint الدفع نفسه) لازم يكون مستثنى من
    IsProviderNotBlocked في كل مكان تاني — الفلاتر بتنادي عليه دايمًا
    عشان تعرف هل تعرض شاشة "لازم تدفع" ولا لأ.
    """
    permission_classes = [IsProvider]

    def get(self, request):
        due, _ = ProviderDue.objects.get_or_create(provider=request.user)
        return Response(ProviderDuesStatusSerializer(due).data, status=status.HTTP_200_OK)


# ==================== محفظة الفني ====================

class ProviderWalletView(APIView):
    """
    GET /provider/wallet/
    الفني يشوف رصيده الحالي وآخر 50 حركة (إيداع نسبة / تحويل / ريفند)
    """
    permission_classes = [IsProvider]

    def get(self, request):
        wallet, _ = ProviderWallet.objects.get_or_create(provider=request.user)
        transactions = wallet.transactions.all()[:50]
        return Response(
            {
                'wallet': ProviderWalletSerializer(wallet).data,
                'recent_transactions': WalletTransactionSerializer(transactions, many=True).data,
            },
            status=status.HTTP_200_OK
        )


# ==================== أدمن — الباتشات الأسبوعية ====================

class AdminPayoutBatchListView(APIView):
    """
    GET /admin/payments/payout-batches/
    الأدمن يشوف كل تشغيلات التحويل الأسبوعية، وكل فني معاه كام،
    عشان يعمل التحويلات البنكية الفعلية بره النظام.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        batches = PayoutBatch.objects.prefetch_related('items__provider').all()
        return Response(PayoutBatchAdminSerializer(batches, many=True).data, status=status.HTTP_200_OK)


class AdminPayoutBatchItemConfirmView(APIView):
    """
    POST /admin/payments/payout-items/<item_id>/confirm/
    body: {"reference_note": "رقم الحوالة أو ملاحظة"}
    الأدمن يأكد إنه حوّل المبلغ فعليًا بنكيًا — ده اللي بيخصم من رصيد المحفظة.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, item_id):
        try:
            item = PayoutBatchItem.objects.select_related('provider').get(id=item_id)
        except PayoutBatchItem.DoesNotExist:
            return Response({'error': 'العنصر غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if item.status == 'transferred':
            return Response({'error': 'تم التحويل بالفعل.'}, status=status.HTTP_400_BAD_REQUEST)

        item.mark_transferred(reference_note=request.data.get('reference_note', ''))

        if not item.batch.items.exclude(status='transferred').exists():
            item.batch.status = 'completed'
            item.batch.save(update_fields=['status'])

        return Response({'message': 'تم تأكيد التحويل بنجاح.'}, status=status.HTTP_200_OK)


class AdminDueCollectionBatchListView(APIView):
    """
    GET /admin/payments/due-collection-batches/
    الأدمن يتابع تشغيلات تحصيل المستحقات ومين دفع ومين لسه.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        batches = DueCollectionBatch.objects.prefetch_related('items__provider').all()
        return Response(DueCollectionBatchAdminSerializer(batches, many=True).data, status=status.HTTP_200_OK)
    

from .models import DueCollectionItem  # موجود بالفعل ضمن الاستيراد
from .serializers import DueCollectionItemPublicSerializer  # أضفها للاستيراد


class DueCollectionItemDetailView(APIView):
    """
    GET /payments/due-collection/<item_id>/
    مفيش IsAuthenticated هنا عمدًا — الفني بيوصل من لينك بره التطبيق
    (Push/SMS) من غير تسجيل دخول. الـ UUID نفسه (غير قابل للتخمين)
    هو التصريح، بالظبط زي أي رابط دفع تجاري (Stripe/Moyasar hosted pages).
    """
    permission_classes = [AllowAny]

    def get(self, request, item_id):
        try:
            item = DueCollectionItem.objects.get(id=item_id)
        except DueCollectionItem.DoesNotExist:
            return Response({'error': 'رابط الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(DueCollectionItemPublicSerializer(item).data, status=status.HTTP_200_OK)


class DueCollectionCallbackView(APIView):
    """
    POST /payments/due-collection/<item_id>/callback/
    بتتنادى من صفحة React بعد ما Moyasar widget يخلص، بنفس فكرة
    PaymentRequestCallbackView بالظبط.
    """
    permission_classes = [AllowAny]

    def post(self, request, item_id):
        payment_id = request.data.get('id')
        if not payment_id:
            return Response({'error': 'payment_id مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = DueCollectionItem.objects.select_related('provider').get(id=item_id)
        except DueCollectionItem.DoesNotExist:
            return Response({'error': 'رابط الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if item.status == 'paid':
            return Response(
                {'status': 'paid', 'item': DueCollectionItemPublicSerializer(item).data},
                status=status.HTTP_200_OK
            )

        try:
            payment_data = get_payment(payment_id)
        except Exception:
            return Response({'error': 'تعذر التحقق من الدفع.'}, status=status.HTTP_502_BAD_GATEWAY)

        payment_status = payment_data.get('status')

        # تحقق إضافي إن الدفع ده فعلاً خاص بالـ item ده، مش item تاني
        metadata = payment_data.get('metadata') or {}
        if metadata.get('due_collection_item_id') and metadata['due_collection_item_id'] != str(item.id):
            return Response({'error': 'بيانات الدفع غير متطابقة.'}, status=status.HTTP_400_BAD_REQUEST)

        if payment_status == 'paid':
            item.moyasar_payment_id = payment_id
            item.save(update_fields=['moyasar_payment_id'])
            _finalize_due_payment(item)

        return Response(
            {'status': payment_status, 'item': DueCollectionItemPublicSerializer(item).data},
            status=status.HTTP_200_OK
        )


@transaction.atomic
def _finalize_due_payment(item):
    item = DueCollectionItem.objects.select_for_update().select_related('provider').get(pk=item.pk)

    if item.status == 'paid':
        return

    item.status  = 'paid'
    item.paid_at = timezone.now()
    item.save(update_fields=['status', 'paid_at'])

    due, _ = ProviderDue.objects.get_or_create(provider=item.provider)
    due.pay(item.amount_due, collection_item=item)

    batch = item.batch
    if not batch.items.exclude(status='paid').exists():
        batch.status = 'completed'
        batch.save(update_fields=['status'])

    transaction.on_commit(lambda: notify_provider_account_unblocked(item.provider_id))

from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from .serializers import AdminDashboardOverviewSerializer


class AdminDashboardOverviewView(APIView):
    """
    GET /admin/payments/dashboard-overview/
    نظرة شاملة سريعة للأدمن: كام فني مقفول، إجمالي المستحقات المعلقة،
    رصيد المحافظ الإجمالي، وأي batch من أسبوع فات لسه مش completed.
    """
    permission_classes = [IsAdminUser]

    # لو الـ batch أقدم من كذا يوم ولسه مش completed، يعتبر "متأخر"
    STALE_THRESHOLD_DAYS = 7

    def get(self, request):
        blocked_dues = ProviderDue.objects.filter(
            is_blocked=True
        ).select_related('provider').order_by('-blocked_at')

        # إجمالي المستحقات المعلقة — على كل الفنيين (مقفولين أو لسه)
        total_outstanding = ProviderDue.objects.filter(
            outstanding_amount__gt=0
        ).aggregate(total=Sum('outstanding_amount'))['total'] or 0

        total_wallet_balance = ProviderWallet.objects.aggregate(
            total=Sum('available_balance')
        )['total'] or 0

        stale_cutoff = timezone.now().date() - timedelta(days=self.STALE_THRESHOLD_DAYS)

        stale_payout_batches = PayoutBatch.objects.filter(
            week_end__lt=stale_cutoff
        ).exclude(status='completed')

        stale_due_batches = DueCollectionBatch.objects.filter(
            week_end__lt=stale_cutoff
        ).exclude(status='completed')

        stale_batches = [
            {
                'batch_type': 'payout',
                'id': b.id,
                'week_start': b.week_start,
                'week_end': b.week_end,
                'status': b.status,
            }
            for b in stale_payout_batches
        ] + [
            {
                'batch_type': 'due_collection',
                'id': b.id,
                'week_start': b.week_start,
                'week_end': b.week_end,
                'status': b.status,
            }
            for b in stale_due_batches
        ]

        data = {
            'blocked_providers_count': blocked_dues.count(),
            'total_outstanding_amount': total_outstanding,
            'total_wallet_balance': total_wallet_balance,
            'blocked_providers': blocked_dues,
            'stale_batches': stale_batches,
        }

        return Response(
            AdminDashboardOverviewSerializer(data).data,
            status=status.HTTP_200_OK
        )
    
class PaymentRequestByCustomRequestView(APIView):
    """
    GET /payments/by-custom-request/<custom_request_id>/
    بتترجع تفاصيل نموذج الدفع بناءً على الـ custom_request_id مباشرة —
    مفيدة للفرونت لما يكون معاه بس رقم الطلب (مش عارف payment_request_id
    لسه) عشان يعرف يوجّه العميل لشاشة الدفع بعد ما الفني يخلّص الشغل.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, custom_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(completion_form__custom_request__id=custom_request_id)
        except PaymentRequest.DoesNotExist:
            return Response(
                {'error': 'لا يوجد نموذج دفع لهذا الطلب بعد.'},
                status=status.HTTP_404_NOT_FOUND
            )

        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type == 'customer' and pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)
        if user_type == 'provider' and pr.provider_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)
    

class ProviderDueDetailView(APIView):
    """
    GET /provider/dues/
    شاشة تفصيلية للفني يشوف فيها مستحقاته الحالية + آخر الحركات —
    توازي ProviderWalletView تمامًا، بس للمستحقات مش المحفظة.
    """
    permission_classes = [IsProvider]

    def get(self, request):
        due, _ = ProviderDue.objects.get_or_create(provider=request.user)
        transactions = due.transactions.all()[:50]
        return Response(
            {
                'due': ProviderDuesStatusSerializer(due).data,
                'recent_transactions': DueTransactionSerializer(transactions, many=True).data,
            },
            status=status.HTTP_200_OK
        )

from decimal import Decimal
from .models import CustomerWallet, CustomerPointsTransaction  # يضاف مع الـ imports فوق
from .serializers import CustomerWalletSerializer, CustomerPointsTransactionSerializer  # يضاف مع الـ imports فوق


class ApplyPointsView(APIView):
    """
    POST /payments/<payment_request_id>/apply-points/
    body: {"points": "30.00"}

    لازم تتنادى قبل select-method. لو العميل عايز يغيّر الكمية، النداء
    ده بيرجع النقاط القديمة (لو موجودة) ويطبّق القيمة الجديدة من غير
    ما يحتاج ينادي remove-points الأول.
    """
    permission_classes = [IsCustomer]

    def post(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.select_related(
                'completion_form__custom_request'
            ).get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        if pr.status != 'awaiting_method':
            return Response(
                {'error': 'لا يمكن استخدام النقاط بعد اختيار طريقة الدفع.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            requested_points = Decimal(str(request.data.get('points', '0')))
        except Exception:
            return Response({'error': 'قيمة النقاط غير صحيحة.'}, status=status.HTTP_400_BAD_REQUEST)

        if requested_points <= 0:
            return Response({'error': 'يجب أن تكون النقاط أكبر من صفر.'}, status=status.HTTP_400_BAD_REQUEST)

        wallet, _ = CustomerWallet.objects.get_or_create(customer=request.user)

        # لو مستخدم نقاط بالفعل على الطلب ده، رجّعها الأول قبل التطبيق الجديد
        if pr.points_used > 0:
            wallet.refund(pr.points_used, payment_request=pr)
            pr.points_used = 0
            pr.points_discount_amount = 0

        # الحد الأقصى = 50% من قيمة الطلب (مفيش علاقة بـ platform_share
        # خالص دلوقتي، لأن الخصم بقى مصروف تسويقي منفصل)
        max_discount = pr.amount * Decimal('0.5')

        if requested_points > wallet.points_balance:
            return Response(
                {'error': f'رصيدك الحالي {wallet.points_balance} نقطة فقط.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if requested_points > max_discount:
            return Response(
                {'error': f'أقصى عدد نقاط يمكن استخدامه لهذا الطلب هو {max_discount} نقطة.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        wallet.redeem(requested_points, payment_request=pr)
        pr.points_used = requested_points
        pr.points_discount_amount = requested_points  # 1 نقطة = 1 ريال
        pr.save(update_fields=['points_used', 'points_discount_amount'])

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)


class RemovePointsView(APIView):
    """
    POST /payments/<payment_request_id>/remove-points/
    العميل يلغي استخدام النقاط اللي طبقها قبل ما يختار طريقة الدفع
    """
    permission_classes = [IsCustomer]

    def post(self, request, payment_request_id):
        try:
            pr = PaymentRequest.objects.get(id=payment_request_id)
        except PaymentRequest.DoesNotExist:
            return Response({'error': 'نموذج الدفع غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        if pr.customer_id != request.user.id:
            return Response({'error': 'غير مصرح.'}, status=status.HTTP_403_FORBIDDEN)

        if pr.status != 'awaiting_method':
            return Response(
                {'error': 'لا يمكن إلغاء النقاط بعد اختيار طريقة الدفع.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if pr.points_used <= 0:
            return Response({'error': 'لا توجد نقاط مستخدمة على هذا الطلب.'}, status=status.HTTP_400_BAD_REQUEST)

        wallet, _ = CustomerWallet.objects.get_or_create(customer=request.user)
        wallet.refund(pr.points_used, payment_request=pr)

        pr.points_used = 0
        pr.points_discount_amount = 0
        pr.save(update_fields=['points_used', 'points_discount_amount'])

        return Response(PaymentRequestSerializer(pr).data, status=status.HTTP_200_OK)


class CustomerWalletView(APIView):
    """
    GET /customer/points-wallet/
    شاشة "نقاطي" للعميل — رصيده وسجل حركاته
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        wallet, _ = CustomerWallet.objects.get_or_create(customer=request.user)
        transactions = wallet.transactions.all()[:50]
        return Response(
            {
                'wallet': CustomerWalletSerializer(wallet).data,
                'recent_transactions': CustomerPointsTransactionSerializer(transactions, many=True).data,
            },
            status=status.HTTP_200_OK
        )