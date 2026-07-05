import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mosaed.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

# لازم ده يتنادى قبل أي import من apps بتاعتنا اللي فيها models
django_asgi_app = get_asgi_application()

from custom_services.middleware import JWTAuthMiddlewareStack
from custom_services.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,

    'websocket': AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})