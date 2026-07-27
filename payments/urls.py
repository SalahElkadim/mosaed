from django.urls import path
from .views import (
    PaymentRequestDetailView,
    PaymentMethodSelectView,
    MoyasarWebhookView,
    ConfirmCashPaymentView,
    ProviderDuesStatusView,
    ProviderWalletView,
    AdminPayoutBatchListView,ApplyPointsView, RemovePointsView, CustomerWalletView,
    AdminPayoutBatchItemConfirmView,ProviderDueDetailView,
    AdminDueCollectionBatchListView,DueCollectionItemDetailView,DueCollectionCallbackView,AdminDashboardOverviewView,PaymentRequestByCustomRequestView
)

urlpatterns = [
    # نموذج الدفع نفسه
    path('payments/<uuid:payment_request_id>/', PaymentRequestDetailView.as_view()),
    path('payments/<uuid:payment_request_id>/select-method/', PaymentMethodSelectView.as_view()),
    path('payments/<uuid:payment_request_id>/confirm-cash/', ConfirmCashPaymentView.as_view()),

    # Webhook ميسر (نفس المسار لكل أنواع الدفع)
    path('payments/webhooks/moyasar/', MoyasarWebhookView.as_view()),

    # الفني — الفلاتر بتنادي عليه دايمًا عشان تعرف تعرض شاشة "لازم تدفع" ولا لأ
    path('provider/dues/status/', ProviderDuesStatusView.as_view()),
    path('provider/wallet/', ProviderWalletView.as_view()),

    # أدمن — الباتشات الأسبوعية
    path('admin/payments/payout-batches/', AdminPayoutBatchListView.as_view()),
    path('admin/payments/payout-items/<uuid:item_id>/confirm/', AdminPayoutBatchItemConfirmView.as_view()),
    path('admin/payments/due-collection-batches/', AdminDueCollectionBatchListView.as_view()),
    path('payments/due-collection/<uuid:item_id>/', DueCollectionItemDetailView.as_view(), name='due-collection-detail'),
    path('payments/due-collection/<uuid:item_id>/callback/', DueCollectionCallbackView.as_view(), name='due-collection-callback'),
    path('admin/payments/dashboard-overview/', AdminDashboardOverviewView.as_view()),
    path('payments/by-custom-request/<uuid:custom_request_id>/',PaymentRequestByCustomRequestView.as_view()),
    path('provider/dues/', ProviderDueDetailView.as_view()),
    path('payments/<uuid:payment_request_id>/apply-points/', ApplyPointsView.as_view()),
    path('payments/<uuid:payment_request_id>/remove-points/', RemovePointsView.as_view()),
    path('customer/points-wallet/', CustomerWalletView.as_view()),
]
