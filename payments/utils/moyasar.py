import requests
from django.conf import settings


def create_payment_link(amount, currency, description, callback_url, metadata=None):
    """
    بينشئ Invoice/Payment Link عبر Moyasar API.
    amount المتوقع هنا بالهللة (smallest currency unit) — لو عندكم القيمة
    بالريال لازم تتحول *100 قبل الإرسال.

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

def get_payment(payment_id):
    """
    يجيب حالة عملية دفع موجودة بالفعل بالـ id بتاعها — مستخدمة في
    الكولباك (بعد الـ 3DS) والـ webhook للتأكد من الحالة الفعلية بدل
    ما نثق في أي بيانات جاية من الفرونت مباشرة.

    بيرجع الـ response الكامل من Moyasar كـ dict (نفس شكل create_payment).
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
