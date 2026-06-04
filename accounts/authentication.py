# accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .models import Customer, Provider, Admin

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_type = validated_token.get('user_type')
        user_id = validated_token.get('user_id')  # USER_ID_CLAIM الافتراضي

        if not user_id or not user_type:
            raise InvalidToken('Token missing required fields')

        try:
            if user_type == 'customer':
                return Customer.objects.get(id=user_id, is_active=True)
            elif user_type == 'provider':
                return Provider.objects.get(id=user_id, is_active=True)
            elif user_type == 'admin':
                return Admin.objects.get(id=user_id, is_active=True)
        except Exception:
            raise InvalidToken('User not found or inactive')