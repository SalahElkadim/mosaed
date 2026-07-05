"""
custom_services/consumers.py
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


# ==================== Helpers لأسماء الجروبات ====================
# نفس الـ helpers دي هنستخدمها في signals.py برضو، عشان أسماء الجروبات
# تطلع متطابقة 100% في الاتنين.

def provider_personal_group(provider_id):
    return f"provider_{provider_id}"


def customer_personal_group(customer_id):
    return f"customer_{customer_id}"


def chat_group(request_id):
    return f"chat_{request_id}"


# ==================== NOTIFICATION CONSUMER ====================

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    اتصال عام واحد لكل يوزر — بيفتح وقت ما التطبيق يفتح ويفضل شغال
    طول ما التطبيق مش مقفول تمامًا.
    """

    async def connect(self):
        user = self.scope.get('user')
        user_type = self.scope.get('user_type')

        if user is None or user_type not in ('customer', 'provider', 'admin'):
            await self.close(code=4001)  # unauthorized
            return

        self.joined_groups = []

        if user_type == 'provider':
            # جروب خاص بيه بس — "طلب جديد في نطاقك" و"تم قبول عرضك" الاتنين
            # بيوصلوا هنا لأن المطابقة الجغرافية (lat/lng) بتتحسب وقت كل طلب
            # جديد في الـ signal، مش وقت الانضمام للجروب (المسافة مش ثابتة).
            personal_group = provider_personal_group(user.id)
            await self.channel_layer.group_add(personal_group, self.channel_name)
            self.joined_groups.append(personal_group)

        elif user_type == 'customer':
            personal_group = customer_personal_group(user.id)
            await self.channel_layer.group_add(personal_group, self.channel_name)
            self.joined_groups.append(personal_group)

        # الأدمن ممكن نضيفله جروب لاحقًا لو احتجنا (مش مطلوب دلوقتي)

        await self.accept()

    async def disconnect(self, close_code):
        for group in getattr(self, 'joined_groups', []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # مش محتاجين نستقبل حاجة من الكلاينت هنا، الاتصال ده للاستماع بس.
        # ممكن نستخدمه مستقبلًا لـ heartbeat/ping لو احتجنا.
        pass

    # ---- الـ handler اللي بيتنادى لما حد يعمل group_send بنوع "notification.message" ----
    async def notification_message(self, event):
        await self.send(text_data=json.dumps(event['payload']))


# ==================== CHAT CONSUMER ====================

@database_sync_to_async
def get_request_and_check_access(request_id, user, user_type):
    """بيتأكد إن اليوزر ده مصرح له يدخل شات الطلب ده"""
    from custom_services.models import CustomRequest

    try:
        obj = CustomRequest.objects.select_related('customer', 'accepted_provider').get(
            id=request_id
        )
    except CustomRequest.DoesNotExist:
        return None

    if user_type == 'customer' and obj.customer_id == user.id:
        return obj
    if user_type == 'provider' and obj.accepted_provider_id == user.id:
        return obj

    return None


@database_sync_to_async
def save_chat_message(custom_request, user, user_type, message_text):
    from custom_services.models import RequestChat

    return RequestChat.objects.create(
        request=custom_request,
        sender_type=user_type,
        sender_id=user.id,
        message=message_text,
    )


class ChatConsumer(AsyncWebsocketConsumer):
    """
    اتصال خاص بشات طلب واحد بالظبط — بيفتح وقت ما شاشة الشات تتفتح.
    """

    async def connect(self):
        user = self.scope.get('user')
        user_type = self.scope.get('user_type')
        self.request_id = self.scope['url_route']['kwargs']['request_id']

        if user is None or user_type not in ('customer', 'provider'):
            await self.close(code=4001)
            return

        custom_request = await get_request_and_check_access(
            self.request_id, user, user_type
        )
        if custom_request is None:
            await self.close(code=4003)  # forbidden
            return

        self.group_name = chat_group(self.request_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            
    async def chat_read(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    async def receive(self, text_data=None, bytes_data=None):
        user = self.scope.get('user')
        user_type = self.scope.get('user_type')

        try:
            data = json.loads(text_data)
            message_text = (data.get('message') or '').strip()
        except (json.JSONDecodeError, AttributeError):
            return

        if not message_text:
            return

        custom_request = await get_request_and_check_access(
            self.request_id, user, user_type
        )
        if custom_request is None:
            return

        chat_message = await save_chat_message(
            custom_request, user, user_type, message_text
        )

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'payload': {
                    'id': str(chat_message.id),
                    'sender_type': user_type,
                    'sender_id': str(user.id),
                    'message': message_text,
                    'created_at': chat_message.created_at.isoformat(),
                }
            }
        )

    # ---- الـ handler اللي بيتنادى لما حد يعمل group_send بنوع "chat.message" ----
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['payload']))