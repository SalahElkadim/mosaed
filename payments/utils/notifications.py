"""
payments/utils/notifications.py

wrapper بسيط حوالين _create_and_send الموجودة في custom_services.signals،
عشان أي حد يبعت إشعار دفع من غير ما يعرف تفاصيل الـ groups والـ payload.
"""
from custom_services.signals import _create_and_send
from custom_services.consumers import provider_personal_group


def notify_provider_payment_received(provider_id, payment_request):
    """العميل دفع أونلاين بنجاح — نبلغ الفني إن نصيبه اتضاف للمحفظة"""
    data = {
        'payment_request_id': str(payment_request.id),
        'amount': str(payment_request.provider_share),
    }
    _create_and_send(
        recipient_type='provider',
        recipient_id=provider_id,
        event='payment_received',
        title='تم استلام دفعة',
        body=f'تم إضافة {payment_request.provider_share} ر.س لمحفظتك',
        data=data,
        group_name=provider_personal_group(provider_id),
    )


def notify_provider_due_payment_required(provider_id, collection_item):
    """بداية الأسبوع — الفني عليه مستحقات ولازم يسددها"""
    data = {
        'collection_item_id': str(collection_item.id),
        'amount_due': str(collection_item.amount_due),
        'payment_link': collection_item.payment_link,
    }
    _create_and_send(
        recipient_type='provider',
        recipient_id=provider_id,
        event='due_payment_required',
        title='مطلوب سداد مستحقات',
        body=f'عليك سداد {collection_item.amount_due} ر.س للاستمرار في استخدام التطبيق',
        data=data,
        group_name=provider_personal_group(provider_id),
    )


def notify_provider_account_unblocked(provider_id):
    """الفني سدد مستحقاته — حسابه اتفتح تاني"""
    _create_and_send(
        recipient_type='provider',
        recipient_id=provider_id,
        event='account_unblocked',
        title='تم فتح حسابك',
        body='تم سداد المستحقات بنجاح، يمكنك استخدام التطبيق بشكل طبيعي الآن',
        data={},
        group_name=provider_personal_group(provider_id),
    )