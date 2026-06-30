from django.urls import path
from .views import (
    # Customer
    CustomerCustomRequestListView,
    CustomerCustomRequestDetailView,
    CustomerCancelRequestView,
    CustomerOfferListView,
    CustomerAcceptOfferView,
    CustomerChatView,
    # Provider
    ProviderCustomRequestListView,
    ProviderCustomRequestDetailView,
    ProviderOfferCreateView,
    ProviderOfferWithdrawView,
    ProviderChatView,
    ProviderCustomCompletionFormView,
    ProviderCustomCompletionMediaView,
    # Admin
    AdminCustomRequestListView,
    AdminCustomRequestDetailView,ProviderBookingListView,
    AdminCustomRequestStatusView,
    AdminExpiredRequestsView,
    AdminCustomRequestOffersView,
    AdminPlatformSettingsView,
)

urlpatterns = [

    # ── Customer ────────────────────────────────────────────────
    path('custom-requests/',
         CustomerCustomRequestListView.as_view(),
         name='customer-custom-requests'),

    path('custom-requests/<uuid:request_id>/',
         CustomerCustomRequestDetailView.as_view(),
         name='customer-custom-request-detail'),

    path('custom-requests/<uuid:request_id>/cancel/',
         CustomerCancelRequestView.as_view(),
         name='customer-cancel-request'),

    path('custom-requests/<uuid:request_id>/offers/',
         CustomerOfferListView.as_view(),
         name='customer-offer-list'),

    path('custom-requests/<uuid:request_id>/offers/<uuid:offer_id>/accept/',
         CustomerAcceptOfferView.as_view(),
         name='customer-accept-offer'),

    path('custom-requests/<uuid:request_id>/chat/',
         CustomerChatView.as_view(),
         name='customer-chat'),

    # ── Provider ────────────────────────────────────────────────
    path('provider/custom-requests/',
         ProviderCustomRequestListView.as_view(),
         name='provider-custom-requests'),

    path('provider/custom-requests/<uuid:request_id>/',
         ProviderCustomRequestDetailView.as_view(),
         name='provider-custom-request-detail'),

    path('provider/custom-requests/<uuid:request_id>/offers/',
         ProviderOfferCreateView.as_view(),
         name='provider-offer-create'),

    path('provider/offers/<uuid:offer_id>/',
         ProviderOfferWithdrawView.as_view(),
         name='provider-offer-withdraw'),

    path('provider/custom-requests/<uuid:request_id>/chat/',
         ProviderChatView.as_view(),
         name='provider-chat'),

    path('provider/custom-requests/<uuid:request_id>/completion/',
         ProviderCustomCompletionFormView.as_view(),
         name='provider-completion-form'),

    path('provider/custom-requests/<uuid:request_id>/completion/media/',
         ProviderCustomCompletionMediaView.as_view(),
         name='provider-completion-media'),

    path('provider/custom-requests/<uuid:request_id>/completion/media/<uuid:media_id>/',
         ProviderCustomCompletionMediaView.as_view(),
         name='provider-completion-media-delete'),

    # ── Admin ────────────────────────────────────────────────────
    path('admin/custom-requests/',
         AdminCustomRequestListView.as_view(),
         name='admin-custom-requests'),

    path('admin/custom-requests/expired/',
         AdminExpiredRequestsView.as_view(),
         name='admin-expired-requests'),

    path('admin/custom-requests/<uuid:request_id>/',
         AdminCustomRequestDetailView.as_view(),
         name='admin-custom-request-detail'),

    path('admin/custom-requests/<uuid:request_id>/status/',
         AdminCustomRequestStatusView.as_view(),
         name='admin-custom-request-status'),

    path('admin/custom-requests/<uuid:request_id>/offers/',
         AdminCustomRequestOffersView.as_view(),
         name='admin-custom-request-offers'),

    path('admin/platform-settings/',
         AdminPlatformSettingsView.as_view(),
         name='admin-platform-settings'),
         path('provider/bookings/', ProviderBookingListView.as_view()),
]