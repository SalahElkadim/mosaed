import requests
from django.conf import settings


def create_payment_link(amount, currency, description, callback_url, metadata=None):
    """
    بينشئ Invoice/Payment Link عبر Moyasar API — مستخدمة في تدفق تحصيل
    مستحقات الفنيين (DueCollectionItem.payment_link).
    amount المتوقع هنا بالريال (بيتحول *100 جوه الدالة نفسها).

    بيرجع dict: {"id": ..., "payment_url": ...}
    """
    response = requests.post(
        f"{settings.MOYASAR_API_URL}/invoices",
        auth=(settings.MOYASAR_SECRET_KEY, ''),
        json={
            'amount': int(amount * 100),
            'currency': currency,
            'description': description,
            'callback_url': callback_url,
            'metadata': metadata or {},
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return {
        'id': data['id'],
        'payment_url': data['url'],
    }


def create_payment(amount_halalas, description, callback_url, token, metadata=None):
    """
    ينفذ دفع مباشر عبر Moyasar Payments API باستخدام token اتولّد في
    المتصفح من Moyasar.js — مستخدمة في نموذج الدفع الأساسي
    (InitiateOnlinePaymentView)، بعكس create_payment_link اللي بترجع
    رابط hosted منفصل.

    amount_halalas متوقع بالهللة بالفعل (الـ caller بيحسبها).

    بيرجع الـ response الكامل من Moyasar، فيه على الأقل:
    id, status, source: {transaction_url, ...} لو محتاج 3DS
    """
    response = requests.post(
        f"{settings.MOYASAR_API_URL}/payments",
        auth=(settings.MOYASAR_SECRET_KEY, ''),
        json={
            'amount': amount_halalas,
            'currency': 'SAR',
            'description': description,
            'callback_url': callback_url,
            'source': {
                'type': 'token',
                'token': token,
            },
            'metadata': metadata or {},
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_payment(payment_id):
    """
    يجيب حالة عملية دفع موجودة بالفعل بالـ id بتاعها — مستخدمة في
    الكولباك (بعد 3DS) والـ webhook، لكل من نموذج الدفع الأساسي
    وتحصيل المستحقات، عشان نتأكد من الحالة الفعلية من مصدر موثوق
    بدل ما نثق ببيانات جاية من الفرونت مباشرة.
    """
    response = requests.get(
        f"{settings.MOYASAR_API_URL}/payments/{payment_id}",
        auth=(settings.MOYASAR_SECRET_KEY, ''),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def verify_webhook_payload(request):
    """
    التحقق من إن الـ webhook فعلاً جاي من Moyasar (مش مزور).
    عدّلها حسب آلية التحقق اللي Moyasar بتوفرها (secret token في header
    أو HMAC signature) — نفس الطريقة المستخدمة أصلاً في تكامل Sabrlingua.
    """
    secret_header = request.headers.get('X-Moyasar-Secret-Token', '')
    return secret_header == getattr(settings, 'MOYASAR_WEBHOOK_SECRET', None)