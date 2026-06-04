
from django.contrib import admin
from django.urls import path,include
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/existedservices/',include('existedservices.urls')),
    path('api/accounts/', include('accounts.urls')),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/custom_services/', include('custom_services.urls')),
    
]
