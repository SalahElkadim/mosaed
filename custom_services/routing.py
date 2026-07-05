"""
custom_services/routing.py

مسارات الـ WebSocket (منفصلة تمامًا عن urls.py العادي بتاع الـ HTTP)
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # اتصال الإشعارات العام — يفتح مرة واحدة وقت ما التطبيق يفتح
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),

    # اتصال الشات — واحد لكل طلب (custom request) وقت ما شاشة الشات تتفتح
    re_path(
        r'^ws/chat/(?P<request_id>[0-9a-f-]+)/$',
        consumers.ChatConsumer.as_asgi()
    ),
]