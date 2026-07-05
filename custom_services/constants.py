"""
custom_services/constants.py (لو اسم الـ app عندك مختلف، حطه في نفس المكان)
"""

# نطاق المطابقة الجغرافية الافتراضي بين الفني وطلبات العملاء (بالكيلومتر)
# نفس الرقم مستخدم في:
#   - ProviderCustomRequestListView / ProviderCustomRequestDetailView (الفلترة)
#   - ServiceOfferCreateSerializer (التحقق وقت إرسال عرض)
#   - signals.py (الإشعارات)
DEFAULT_SERVICE_RADIUS_KM = 30