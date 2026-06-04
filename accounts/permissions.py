# accounts/permissions.py

from rest_framework.permissions import BasePermission
from .models import Admin, Customer, Provider


class IsAdminUser(BasePermission):
    """
    أي أدمن سواء main أو staff
    """
    message = "Access restricted to admins only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None
        return (
            request.user and
            request.user.is_authenticated and
            token_user_type == 'admin' and
            isinstance(request.user, Admin)
        )


class IsMainAdmin(BasePermission):
    """
    Main Admin بس - للعمليات الحساسة
    """
    message = "Access restricted to main admins only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None
        return (
            request.user and
            request.user.is_authenticated and
            token_user_type == 'admin' and
            isinstance(request.user, Admin) and
            request.user.role == 'main_admin'
        )


class IsStaffAdmin(BasePermission):
    """
    Staff Admin بس
    """
    message = "Access restricted to staff admins only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None
        return (
            request.user and
            request.user.is_authenticated and
            token_user_type == 'admin' and
            isinstance(request.user, Admin) and
            request.user.role == 'staff_admin'
        )


class HasAdminPermission(BasePermission):
    """
    بيتبعتله اسم الـ permission المطلوب
    Main Admin عنده كل الصلاحيات تلقائياً
    Staff Admin بيتحقق من الـ custom_permissions بتاعته
    الاستخدام:
        permission_classes = [HasAdminPermission]
        required_permission = 'can_approve_providers'
    """
    message = "You don't have permission to perform this action."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None

        if not (request.user and request.user.is_authenticated and
                token_user_type == 'admin' and isinstance(request.user, Admin)):
            return False

        # Main Admin عنده كل حاجة
        if request.user.role == 'main_admin':
            return True

        # Staff Admin بيتحقق من الـ permission المطلوبة في الـ View
        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return False

        return request.user.has_custom_permission(required_permission)


class IsCustomer(BasePermission):
    """
    Customer معمول له verify
    """
    message = "Access restricted to verified customers only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None
        return (
            request.user and
            request.user.is_authenticated and
            token_user_type == 'customer' and
            isinstance(request.user, Customer) and
            request.user.is_phone_verified and
            request.user.is_active
        )


class IsProvider(BasePermission):
    """
    Provider معمول له verify وموافق عليه من الأدمن
    """
    message = "Access restricted to approved providers only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None
        return (
            request.user and
            request.user.is_authenticated and
            token_user_type == 'provider' and
            isinstance(request.user, Provider) and
            request.user.is_phone_verified and
            request.user.is_approved and
            request.user.is_active
        )


class IsProviderOrCustomer(BasePermission):
    """
    للـ endpoints اللي تنفع للاتنين
    """
    message = "Access restricted to customers or providers only."

    def has_permission(self, request, view):
        token_user_type = request.auth.get('user_type') if request.auth else None

        if token_user_type == 'customer' and isinstance(request.user, Customer):
            return (
                request.user.is_authenticated and
                request.user.is_phone_verified and
                request.user.is_active
            )

        if token_user_type == 'provider' and isinstance(request.user, Provider):
            return (
                request.user.is_authenticated and
                request.user.is_phone_verified and
                request.user.is_approved and
                request.user.is_active
            )

        return False
    
class IsCustomerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        return user_type in ('customer', 'admin')
    
class IsProviderOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        return user_type in ('provider', 'admin')