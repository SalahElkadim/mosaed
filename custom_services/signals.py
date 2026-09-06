
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .utils.geo import is_provider_within_range
from .utils.fcm import send_push_to_tokens
from .models import CustomRequest, ServiceOffer, RequestChat, Notification, DeviceToken
from .consumers import provider_personal_group, customer_personal_group
from .constants import DEFAULT_SERVICE_RADIUS_KM


def _send_to_group(group_name, payload):
    """بيبعت رسالة على جروب معين — sync wrapper حوالين الـ async channel layer"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'notification.message',  # لازم يتطابق مع اسم الـ method في الـ Consumer
            'payload': payload,
        }
    )


def _create_and_send(recipient_type, recipient_id, event, title, body, data, group_name):
    """
    بيعمل الحاجتين اللي لازم يحصلوا مع بعض لأي إشعار:
    1) يخزن سجل Notification في الداتابيز
    2) يبعته لحظيًا على الـ WebSocket (مع notification_id عشان mark-as-read)
    """
    notification = Notification.objects.create(
        recipient_type=recipient_type,
        recipient_id=str(recipient_id),
        event=event,
        title=title,
        body=body,
        data=data,
    )

    payload = dict(data)
    payload.update({
        'event': event,
        'notification_id': str(notification.id),
        'title': title,
        'body': body,
        'created_at': notification.created_at.isoformat(),
    })

    # مهم: نستنى الـ transaction يخلص commit فعليًا قبل ما نبعت أي حاجة
    # (WebSocket أو Push) للخارج. لو بعتنا فورًا وحصل rollback بعد كده،
    # يبقى العميل/الفني استقبل إشعار عن حدث اتلغى ومحصلش في الداتابيز أصلاً.
    # لو مفيش transaction مفتوحة أصلاً، on_commit بينفذ فورًا زي ما هو.
    transaction.on_commit(lambda: _send_to_group(group_name, payload))
    transaction.on_commit(
        lambda: _send_push_notification(recipient_type, recipient_id, title, body, payload)
    )
    return notification


def _send_push_notification(recipient_type, recipient_id, title, body, data):
    """
    بيبعت push notification (FCM) لكل أجهزة اليوزر المسجلة، وبيحذف
    أي توكن اتبين إنه غير صالح (uninstall أو انتهاء صلاحية).

    ده منفصل تمامًا عن الـ WebSocket send — فشله (زي مشكلة اتصال بـ FCM)
    ميأثرش على تخزين الإشعار أو البث اللحظي، لأن الاتنين مستقلين عن بعض.
    """
    tokens = list(
        DeviceToken.objects.filter(
            recipient_type=recipient_type,
            recipient_id=str(recipient_id),
        ).values_list('token', flat=True)
    )
    if not tokens:
        return

    result = send_push_to_tokens(tokens, title=title, body=body, data=data)

    invalid_tokens = result.get('invalid_tokens') or []
    if invalid_tokens:
        DeviceToken.objects.filter(token__in=invalid_tokens).delete()


# ==================== 1) طلب جديد → إشعار للفنيين المتوافقين ====================

@receiver(post_save, sender=CustomRequest)
def notify_providers_on_new_request(sender, instance, created, **kwargs):
    if not created:
        return

    from accounts.models import Provider

    address = instance.address
    if not address or address.lat is None or address.lng is None:
        # مفيش إحداثيات على عنوان الطلب، مش هنقدر نحسب مسافة لحد
        return

    request_lat = float(address.lat)
    request_lng = float(address.lng)

    # كل الفنيين المتوافقين في التخصص، النشطين والمعتمدين، مع عناوينهم
    providers = Provider.objects.filter(
        specialization_id=instance.specialization_id,
        is_active=True,
        is_approved=True,
    ).prefetch_related('addresses')

    description_preview = (instance.description or '')[:100]
    specialization_name = instance.specialization.name if instance.specialization else None

    for provider in providers:
        within_range, distance = is_provider_within_range(
            provider, request_lat, request_lng, DEFAULT_SERVICE_RADIUS_KM
        )
        if not within_range:
            continue

        data = {
            'request_id': str(instance.id),
            'title': instance.title,
            'description_preview': description_preview,
            'specialization_name': specialization_name,
            'scheduled_date': instance.scheduled_date.isoformat() if instance.scheduled_date else None,
            'distance_km': round(distance, 2),
        }

        _create_and_send(
            recipient_type='provider',
            recipient_id=provider.id,
            event='new_custom_request',
            title='طلب خدمة جديد في منطقتك',
            body=f"{instance.title} — على بعد {round(distance, 2)} كم",
            data=data,
            group_name=provider_personal_group(provider.id),
        )


# ==================== 2) عرض جديد → إشعار للعميل ====================
# ==================== 3) قبول عرض → إشعار للفني ====================

@receiver(pre_save, sender=ServiceOffer)
def _cache_old_offer_status(sender, instance, **kwargs):
    """
    بنخزن الحالة القديمة قبل الحفظ عشان نقدر نتأكد وقت الـ post_save
    إن التحديث ده فعلاً تحويل لـ accepted، حتى لو حد عمل save() عادي
    من غير ما يحدد update_fields صراحة.
    """
    if instance.pk:
        try:
            instance._old_status = ServiceOffer.objects.get(pk=instance.pk).status
        except ServiceOffer.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=ServiceOffer)
def notify_on_offer_events(sender, instance, created, **kwargs):
    if created:
        # عرض جديد وصل → نبلغ العميل صاحب الطلب
        custom_request = instance.request

        data = {
            'request_id': str(custom_request.id),
            'offer_id': str(instance.id),
            'provider_name': instance.provider.name,
            'average_rating': str(instance.provider.average_rating),
            'final_price': str(instance.final_price),
            'note': instance.note,
        }

        _create_and_send(
            recipient_type='customer',
            recipient_id=custom_request.customer_id,
            event='new_offer',
            title='عرض جديد على طلبك',
            body=f"{instance.provider.name} عرض {instance.final_price} ر.س",
            data=data,
            group_name=customer_personal_group(custom_request.customer_id),
        )
        return

    # مش إنشاء جديد — نتأكد إن الحالة اتغيرت فعليًا من حاجة تانية لـ accepted
    old_status = getattr(instance, '_old_status', None)
    if old_status != 'accepted' and instance.status == 'accepted':
        data = {
            'request_id': str(instance.request_id),
            'offer_id': str(instance.id),
            'title': instance.request.title,
        }

        _create_and_send(
            recipient_type='provider',
            recipient_id=instance.provider_id,
            event='offer_accepted',
            title='تم قبول عرضك',
            body=f"العميل وافق على عرضك في طلب: {instance.request.title}",
            data=data,
            group_name=provider_personal_group(instance.provider_id),
        )


# ==================== 4) رسالة شات جديدة → إشعار للطرف التاني ====================

@receiver(post_save, sender=RequestChat)
def notify_on_new_chat_message(sender, instance, created, **kwargs):
    if not created:
        return

    custom_request = instance.request

    # حدد مين الطرف التاني (مش اللي بعت الرسالة) ومين الـ recipient
    if instance.sender_type == 'customer':
        if not custom_request.accepted_provider_id:
            return
        recipient_type = 'provider'
        recipient_id = custom_request.accepted_provider_id
        group_name = provider_personal_group(custom_request.accepted_provider_id)
    else:  # sender_type == 'provider'
        recipient_type = 'customer'
        recipient_id = custom_request.customer_id
        group_name = customer_personal_group(custom_request.customer_id)

        data = {
        'request_id': str(custom_request.id),
        'sender_type': instance.sender_type,
        'message_type': instance.message_type,
        }

        body_map = {
            'image': '📷 صورة',
            'voice': '🎤 رسالة صوتية',
            'file': f'📎 {instance.file_name or "ملف"}',
        }
        notification_body = instance.message[:80] if instance.message else body_map.get(
            instance.message_type, 'رسالة جديدة'
        )

        _create_and_send(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            event='new_chat_message',
            title='رسالة جديدة',
            body=notification_body,
            data=data,
            group_name=group_name,
        )