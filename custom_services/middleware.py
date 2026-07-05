"""
custom_services/middleware.py

بيتحقق من الـ JWT token اللي بيتبعت كـ query parameter وقت فتح اتصال الـ WebSocket.
مثال على الرابط اللي هيستخدمه Iman من الفلاتر:

    wss://mosaed-production.up.railway.app/ws/notifications/?token=<access_token>
    wss://mosaed-production.up.railway.app/ws/chat/<request_id>/?token=<access_token>

بما إن المشروع مش بيستخدم AUTH_USER_MODEL عادي (زي ما شايفين في accounts/views.py
get_tokens_for_user)، مش هنقدر نستخدم AuthMiddlewareStack الجاهزة بتاعة Channels
(هي مبنية على Django sessions/auth عادي). لذلك بنعمل middleware مخصص.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


@database_sync_to_async
def get_user_from_payload(user_id, user_type):
    """بيجيب الـ Customer/Provider/Admin object حسب نوعه من التوكن"""
    from accounts.models import Customer, Provider, Admin

    try:
        if user_type == 'customer':
            return Customer.objects.get(id=user_id, is_active=True), user_type
        elif user_type == 'provider':
            return Provider.objects.get(id=user_id, is_active=True), user_type
        elif user_type == 'admin':
            return Admin.objects.get(id=user_id, is_active=True), user_type
    except (Customer.DoesNotExist, Provider.DoesNotExist, Admin.DoesNotExist):
        return None, None

    return None, None


class JWTAuthMiddleware(BaseMiddleware):
    """
    بيتحقق من الـ token ويحط الـ user و user_type في الـ scope
    عشان الـ Consumers تقدر تستخدمهم.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token_list = query_params.get('token')

        scope['user'] = None
        scope['user_type'] = None

        if token_list:
            token = token_list[0]
            try:
                access_token = AccessToken(token)
                user_id = access_token.get('user_id')
                user_type = access_token.get('user_type')

                if user_id and user_type:
                    user, resolved_type = await get_user_from_payload(user_id, user_type)
                    scope['user'] = user
                    scope['user_type'] = resolved_type

            except (TokenError, InvalidToken):
                scope['user'] = None
                scope['user_type'] = None

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)