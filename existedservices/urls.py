from django.urls import path
from .views import (
    # Client - Services
    ExistedServiceListView,
    ExistedServiceDetailView,
    # Admin - Services
    AdminExistedServiceListView,
    AdminExistedServiceDetailView,
    # Admin - Attributes
    AdminServiceAttributeListView,
    AdminServiceAttributeDetailView,    AdminConfirmPriceOnBehalfView,

    ProviderBookingStatusView,
    # Client - Bookings
    CustomerBookingListView,
    CustomerBookingDetailView,
    CustomerBookingPriceDecisionView,
    ProviderPreviousWorkView,
    ProviderBookingDetailView,
    # Admin - Bookings
    AdminBookingListView,
    AdminBookingDetailView,
    ServicePreviousWorksView,
    AdminBookingStatusView,
    AdminBookingSetPriceView,
    ServiceProviderListView,
    AdminServiceProviderListView,
    AdminServiceProviderDetailView,
    ServiceReviewListView,
    ServiceRatingSummaryView,
    AdminReviewDeleteView,
    AdminServiceReviewsClearView,
    AdminServiceWarrantyView,
    AdminBookingAssignProviderView,
    ProviderCompletionFormView,
    CustomerCompletionFormView,
    ProviderCompletionMediaView,
    CustomerConfirmProviderArrivalView,
    AdminAvailableProvidersForServiceView,
    ProviderCompletionFormListView,
)

urlpatterns = [
    # ==================== CLIENT - SERVICES ====================
    path('existed/', ExistedServiceListView.as_view(), name='existed-service-list'),
    path('existed/<uuid:service_id>/', ExistedServiceDetailView.as_view(), name='existed-service-detail'),

    # ==================== ADMIN - SERVICES ====================
    path('admin/existed/', AdminExistedServiceListView.as_view(), name='admin-existed-service-list'),
    path('admin/existed/<uuid:service_id>/', AdminExistedServiceDetailView.as_view(), name='admin-existed-service-detail'),

    # ==================== ADMIN - ATTRIBUTES ====================
    path('admin/existed/<uuid:service_id>/attributes/', AdminServiceAttributeListView.as_view(), name='admin-attribute-list'),
    path('admin/existed/<uuid:service_id>/attributes/<uuid:attribute_id>/', AdminServiceAttributeDetailView.as_view(), name='admin-attribute-detail'),

    # ==================== CLIENT - BOOKINGS ====================
    path('bookings/', CustomerBookingListView.as_view(), name='customer-booking-list'),
    path('bookings/<uuid:booking_id>/', CustomerBookingDetailView.as_view(), name='customer-booking-detail'),
    path('bookings/<uuid:booking_id>/cancel/', CustomerBookingDetailView.as_view(), name='customer-booking-cancel'),
    path('bookings/<uuid:booking_id>/price-decision/', CustomerBookingPriceDecisionView.as_view(), name='customer-booking-price-decision'),

    # ==================== ADMIN - BOOKINGS ====================
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin-booking-list'),
    path('admin/bookings/<uuid:booking_id>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),
    path('admin/bookings/<uuid:booking_id>/status/', AdminBookingStatusView.as_view(), name='admin-booking-status'),
    path('admin/bookings/<uuid:booking_id>/set-price/', AdminBookingSetPriceView.as_view(), name='admin-booking-set-price'),
    path('admin/bookings/<uuid:booking_id>/assign-provider/', AdminBookingAssignProviderView.as_view(), name='admin-booking-assign-provider'),

    # ==================== SERVICE PROVIDERS ====================
    # Client
    path('services/<uuid:service_id>/providers/', ServiceProviderListView.as_view(), name='service-providers'),

    # Admin
    path('admin/services/<uuid:service_id>/providers/', AdminServiceProviderListView.as_view(), name='admin-service-providers'),
    path('admin/services/<uuid:service_id>/providers/<uuid:sp_id>/', AdminServiceProviderDetailView.as_view(), name='admin-service-provider-detail'),
    path('admin/services/<uuid:service_id>/available-providers/', AdminAvailableProvidersForServiceView.as_view(), name='admin-available-providers'),

    # ==================== WARRANTY ====================
    path('admin/services/<uuid:service_id>/warranty/', AdminServiceWarrantyView.as_view(), name='admin-service-warranty'),

    # ==================== REVIEWS ====================
    path('services/<uuid:service_id>/reviews/clear/', AdminServiceReviewsClearView.as_view(), name='service-reviews-clear'),
    path('services/<uuid:service_id>/reviews/', ServiceReviewListView.as_view(), name='service-reviews'),
    path('services/<uuid:service_id>/rating/', ServiceRatingSummaryView.as_view(), name='service-rating'),
    path('reviews/<uuid:review_id>/', AdminReviewDeleteView.as_view(), name='service-review-delete'),

    # ==================== COMPLETION FORMS ====================
    # Provider
    path('provider/completion-forms/<uuid:booking_id>/', ProviderCompletionFormView.as_view(), name='provider-completion-form'),
    path('provider/completion-forms/<uuid:booking_id>/media/', ProviderCompletionMediaView.as_view(), name='provider-completion-media'),
    path('provider/completion-forms/<uuid:booking_id>/media/<uuid:media_id>/', ProviderCompletionMediaView.as_view(), name='provider-completion-media-detail'),
    path('provider/completion-forms/', ProviderCompletionFormListView.as_view(), name='provider-completion-form-list'),

    # Client
    path('bookings/<uuid:booking_id>/completion/', CustomerCompletionFormView.as_view(), name='customer-completion-form'),
    path('bookings/<uuid:booking_id>/provider-arrived/', CustomerConfirmProviderArrivalView.as_view(), name='customer-confirm-provider-arrival'),

    # ==================== PREVIOUS WORKS ====================
    # Client
    path('services/<uuid:service_id>/previous-works/', ServicePreviousWorksView.as_view(), name='service-previous-works'),

    # Provider / Admin
    path('bookings/<uuid:booking_id>/previous-work/', ProviderPreviousWorkView.as_view(), name='booking-previous-work'),

    # ==================== PROVIDER - BOOKINGS ====================
    path('provider/bookings/<uuid:booking_id>/', ProviderBookingDetailView.as_view(), name='provider-booking-detail'),
    path('provider/bookings/<uuid:booking_id>/status/', ProviderBookingStatusView.as_view(), name='provider-booking-status'),
    path('admin/bookings/<uuid:booking_id>/confirm-price/', AdminConfirmPriceOnBehalfView.as_view(), name='admin-booking-confirm-price'),
]