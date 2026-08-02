from django.urls import path
from .views import (
    AdminLoginView,
    SendOTPView, VerifyOTPView,
    CustomerRegisterView, ProviderRegisterView,
    LogoutView,
    CustomerProfileView, ProviderProfileView,
    ProviderBlockView,AdminMarketingCodeListView, AdminMarketingCodeDetailView, AdminMarketingCodeUsageView,
    ProviderListView,
    ProviderDetailView,ProviderApproveView,RegisterBiometricView, BiometricLoginView, RevokeBiometricView,
    CustomerAddressView, CustomerAddressDetailView, ReviewCreateView,CityListView,ProviderAddressView,CityDetailView,
    ProviderReviewsView,RegionDetailView,RegionListView,
    ReviewDeleteView, ReviewUpdateView,AdminCustomerDetailView,AdminCustomerListView,ProviderAddressDetailView,
    ProviderReviewsDeleteAllView,PreviousWorkListCreateView,AdminProviderAddressDetailView, PreviousWorkDetailView,NearbyProvidersView, SpecializationListView,AdminProviderAddressView, SpecializationDetailView,
)

urlpatterns = [
    # Admin
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),

    # OTP
    path('otp/send/', SendOTPView.as_view(), name='send-otp'),
    path('otp/verify/', VerifyOTPView.as_view(), name='verify-otp'),

    # Register
    path('customer/register/', CustomerRegisterView.as_view(), name='customer-register'),
    path('provider/register/', ProviderRegisterView.as_view(), name='provider-register'),

    # Logout
    path('logout/', LogoutView.as_view(), name='logout'),

    # Profile
    path('customer/profile/', CustomerProfileView.as_view(), name='customer-profile'),
    path('provider/profile/', ProviderProfileView.as_view(), name='provider-profile'),
    path('admin/providers/', ProviderListView.as_view(), name='provider-list'),
    path('admin/providers/<uuid:provider_id>/', ProviderDetailView.as_view(), name='provider-detail'),
    path('admin/providers/<uuid:provider_id>/block/', ProviderBlockView.as_view(), name='provider-block'),
    path('admin/providers/<uuid:provider_id>/approve/', ProviderApproveView.as_view(), name='provider-approve'),  # ✅ إضافة
    path('biometric/register/', RegisterBiometricView.as_view(), name='biometric-register'),
    path('biometric/login/',    BiometricLoginView.as_view(),    name='biometric-login'),
    path('biometric/revoke/',   RevokeBiometricView.as_view(),   name='biometric-revoke'),
    path('customer/addresses/',             CustomerAddressView.as_view(),       name='customer-addresses'),
    path('customer/addresses/<uuid:address_id>/', CustomerAddressDetailView.as_view(), name='customer-address-detail'),
    # cities & regions
    path('cities/', CityListView.as_view()),
    path('cities/<uuid:city_id>/', CityDetailView.as_view()),
    path('regions/', RegionListView.as_view()),
    path('regions/<uuid:region_id>/', RegionDetailView.as_view()),

    # provider addresses
    path('provider/addresses/', ProviderAddressView.as_view()),
    path('provider/addresses/<uuid:address_id>/', ProviderAddressDetailView.as_view()),

    # Reviews
    path('reviews/', ReviewCreateView.as_view(), name='review-create'),
    path('reviews/provider/<uuid:provider_id>/all/', ProviderReviewsDeleteAllView.as_view(), name='provider-reviews-delete-all'),  # ← الأول
    path('reviews/provider/<uuid:provider_id>/', ProviderReviewsView.as_view(), name='provider-reviews'),                          # ← الثاني
    path('reviews/<uuid:review_id>/', ReviewDeleteView.as_view(), name='review-delete'),
    path('reviews/<uuid:review_id>/edit/', ReviewUpdateView.as_view()),
    path('previousworks/', PreviousWorkListCreateView.as_view()),                          # POST — الفني يضيف
    path('previousworks/provider/<uuid:provider_id>/', PreviousWorkListCreateView.as_view()),  # GET — عرض للكل
    path('previousworks/<uuid:work_id>/', PreviousWorkDetailView.as_view()), 
    path('specializations/', SpecializationListView.as_view()),
    path('specializations/<uuid:spec_id>/', SpecializationDetailView.as_view()),
    path('admin/customers/',                  AdminCustomerListView.as_view()),
    path('admin/customers/<uuid:customer_id>/', AdminCustomerDetailView.as_view()),
    # في urls.py أضيف:
    path('admin/providers/<uuid:provider_id>/addresses/', AdminProviderAddressView.as_view()),
    path('admin/providers/<uuid:provider_id>/addresses/<uuid:address_id>/', AdminProviderAddressDetailView.as_view()),
    path('providers/nearby/', NearbyProvidersView.as_view(), name='nearby-providers'),
    path('admin/marketing-codes/', AdminMarketingCodeListView.as_view()),
    path('admin/marketing-codes/<uuid:code_id>/', AdminMarketingCodeDetailView.as_view()),
    path('admin/marketing-codes/<uuid:code_id>/usages/', AdminMarketingCodeUsageView.as_view()),
]
    


