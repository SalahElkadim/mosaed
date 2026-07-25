from rest_framework.permissions import BasePermission
from .models import ProviderDue


class IsProviderNotBlocked(BasePermission):
    """
    تتطبق على كل الـ views الخاصة بالفني في custom_services (وأي مكان
    تاني هيتضاف لاحقًا). بتمنع أي فني عليه مستحقات متأخرة (is_blocked)
    من عمل أي حاجة غير مراجعة حالة الدفع بتاعته وتسديدها.

    الـ endpoint بتاع حالة المستحقات نفسه ورابط الدفع لازم يكونوا
    مستثنيين من الـ permission ده — بيتحققوا بـ IsAuthenticated/IsProvider
    عادي في views.py الخاصة بيهم.
    """

    message = 'لديك مستحقات متأخرة على المنصة. يرجى السداد للاستمرار في استخدام التطبيق.'

    def has_permission(self, request, view):
        user_type = getattr(request.auth, 'payload', {}).get('user_type')
        if user_type != 'provider':
            return True  # مش فني — الـ permission ده مالوش دعوة بيه

        due = ProviderDue.objects.filter(provider=request.user).first()
        if not due:
            return True  # لسه مفيش مستحقات اتسجلت عليه خالص

        return not due.is_blocked
