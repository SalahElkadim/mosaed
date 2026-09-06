from django.urls import path
from .views import (
    # Customer
    CustomerCustomRequestListView,
    CustomerCustomRequestDetailView,
    CustomerCancelRequestView,
    CustomerOfferListView,
    CustomerAcceptOfferView,
    CustomerChatView,DeviceTokenView,OnboardingListView,CustomerAppMessageListView,ProviderAppMessageListView,
    # Provider
    ProviderCustomRequestListView,
    ProviderCustomRequestDetailView,AdminAppMessageListView,AdminAppMessageDetailView,AdminOnboardingSlideListView,
    ProviderOfferCreateView,
    ProviderOfferWithdrawView,ProviderCustomCompletionFormListView,AdminOnboardingSlideDetailView,
    ProviderChatView,CustomerCustomCompletionFormView,
    ProviderCustomCompletionFormView,
    ProviderCustomCompletionMediaView,ProviderCustomPreviousWorkView,
    # Admin
    AdminCustomRequestListView,
    AdminCustomRequestDetailView,ProviderBookingListView,
    AdminCustomRequestStatusView,
    AdminExpiredRequestsView,
    AdminCustomRequestOffersView,
    AdminPlatformSettingsView,NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,CustomerConversationsListView,
    CustomerChatMarkReadView,
    ProviderChatMarkReadView,ProviderMyOffersListView,CustomerConfirmProviderArrivalCustomRequestView
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


    path('provider/offers/', ProviderMyOffersListView.as_view(), name='provider-my-offers'),
    path('provider/offers/<uuid:offer_id>/',
         ProviderOfferWithdrawView.as_view(),
         name='provider-offer-withdraw'),
     path('onboarding/', OnboardingListView.as_view(), name='onboarding-list'),


     


    path('provider/custom-requests/<uuid:request_id>/chat/',
         ProviderChatView.as_view(),
         name='provider-chat'),

     path('provider/custom-requests/completion-forms/',
     ProviderCustomCompletionFormListView.as_view(),
     name='provider-custom-completion-forms-list'),
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

    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('notifications/<uuid:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('custom-requests/<uuid:request_id>/chat/read/',
     CustomerChatMarkReadView.as_view(),
     name='customer-chat-mark-read'),
 
# ── Provider chat read ──
     path('provider/custom-requests/<uuid:request_id>/chat/read/',
     ProviderChatMarkReadView.as_view(),
     name='provider-chat-mark-read'),
     path('device-tokens/', DeviceTokenView.as_view(), name='device-token'),
     path('custom-requests/<uuid:request_id>/provider-arrived/',CustomerConfirmProviderArrivalCustomRequestView.as_view(),name='custom-request-provider-arrived'
),
     path('provider/custom-requests/<uuid:request_id>/previous-work/',
     ProviderCustomPreviousWorkView.as_view(),
     name='provider-custom-previous-work'),
     # custom_services/urls.py

path('custom-requests/<uuid:request_id>/completion/',
     CustomerCustomCompletionFormView.as_view(),
     name='customer-custom-completion-form'),

     path('customer/messages/', CustomerAppMessageListView.as_view(), name='customer-app-messages'),
    path('provider/messages/', ProviderAppMessageListView.as_view(), name='provider-app-messages'),
     path('admin/messages/', AdminAppMessageListView.as_view(), name='admin-app-messages'),
    path('admin/messages/<uuid:message_id>/', AdminAppMessageDetailView.as_view(), name='admin-app-message-detail'),
    path('admin/onboarding/', AdminOnboardingSlideListView.as_view(), name='admin-onboarding-list'),
    path('admin/onboarding/<uuid:slide_id>/', AdminOnboardingSlideDetailView.as_view(), name='admin-onboarding-detail'),
    path('custom-requests/conversations/', CustomerConversationsListView.as_view(), name='customer-conversations'),
]

     



