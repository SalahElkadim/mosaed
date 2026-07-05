"""
utils/geo.py

دالة مشتركة لحساب المسافة بين نقطتين (lat/lng) عشان نستخدمها في:
- accounts/views.py (NearbyProvidersView)
- custom_requests/views.py (فلترة الطلبات المتاحة للفني)
- custom_requests/serializers.py (التحقق وقت إرسال عرض)
- custom_services/signals.py (إشعارات الطلب الجديد)

كده الحساب مكتوب مرة واحدة بس، ولو احتجنا نغيّره أو نحسّنه، بنغيّره في مكان واحد.
"""

from math import radians, sin, cos, sqrt, atan2


def haversine_km(lat1, lng1, lat2, lng2):
    """المسافة بالكيلومتر بين نقطتين جغرافيتين"""
    R = 6371
    lat1, lng1, lat2, lng2 = map(radians, [float(lat1), float(lng1), float(lat2), float(lng2)])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def get_provider_default_address(provider):
    """
    بيرجع العنوان الافتراضي بتاع الفني (لو موجود وعنده إحداثيات)، وإلا None.
    لو الـ provider.addresses أصلاً متجابة بـ prefetch_related، الدالة دي
    مش هتعمل query إضافي.
    """
    for address in provider.addresses.all():
        if address.is_default and address.lat is not None and address.lng is not None:
            return address
    return None


def is_provider_within_range(provider, target_lat, target_lng, radius_km):
    """
    بيرجع (True/False, distance_km).
    لو الفني مفيش عنده عنوان افتراضي بإحداثيات، بيرجع (False, None).
    """
    address = get_provider_default_address(provider)
    if not address:
        return False, None

    distance = haversine_km(target_lat, target_lng, address.lat, address.lng)
    return distance <= radius_km, distance