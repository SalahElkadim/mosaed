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
    AdminServiceAttributeDetailView,
    # Client - Bookings
    CustomerBookingListView,
    CustomerBookingDetailView,
    # Admin - Bookings
    AdminBookingListView,
    AdminBookingDetailView,
    AdminBookingStatusView,
    ServiceProviderListView,AdminServiceProviderListView,AdminServiceProviderDetailView,ServiceReviewListView,
    ServiceRatingSummaryView,
    AdminReviewDeleteView,
    AdminServiceReviewsClearView,AdminServiceWarrantyView,AdminBookingAssignProviderView,
    ProviderCompletionFormView,
    ProviderCompletionMediaView,
    CouponValidateView,
    AdminCouponListView,AdminCouponDetailView,AdminAvailableProvidersForServiceView
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

    # ==================== ADMIN - BOOKINGS ====================
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin-booking-list'),
    path('admin/bookings/<uuid:booking_id>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),
    path('admin/bookings/<uuid:booking_id>/status/', AdminBookingStatusView.as_view(), name='admin-booking-status'),
     # Client
    path('services/<uuid:service_id>/providers/',
         ServiceProviderListView.as_view()),
 
    # Admin
    path('admin/services/<uuid:service_id>/providers/',
         AdminServiceProviderListView.as_view()),
 
    path('admin/services/<uuid:service_id>/providers/<uuid:sp_id>/',
         AdminServiceProviderDetailView.as_view()),
    path('admin/services/<uuid:service_id>/warranty/', AdminServiceWarrantyView.as_view()),
    path('services/<uuid:service_id>/reviews/clear/',   AdminServiceReviewsClearView.as_view(),  name='service-reviews-clear'),
    path('services/<uuid:service_id>/reviews/',         ServiceReviewListView.as_view(),        name='service-reviews'),
    path('services/<uuid:service_id>/rating/',          ServiceRatingSummaryView.as_view(),      name='service-rating'),
    path('reviews/<uuid:review_id>/',                   AdminReviewDeleteView.as_view(),         name='service-review-delete'),
    # Provider
     path('provider/completion-forms/<uuid:booking_id>/',
          ProviderCompletionFormView.as_view()),

     path('provider/completion-forms/<uuid:booking_id>/media/',
          ProviderCompletionMediaView.as_view()),

     path('provider/completion-forms/<uuid:booking_id>/media/<uuid:media_id>/',
          ProviderCompletionMediaView.as_view()),
     # Client
     path('coupons/validate/', CouponValidateView.as_view()),

     # Admin
     path('admin/coupons/',             AdminCouponListView.as_view()),
     path('admin/coupons/<uuid:coupon_id>/', AdminCouponDetailView.as_view()),
     path('admin/services/<uuid:service_id>/available-providers/', 
     AdminAvailableProvidersForServiceView.as_view()),
     path('admin/bookings/<uuid:booking_id>/assign-provider/', 
     AdminBookingAssignProviderView.as_view()),
    
]