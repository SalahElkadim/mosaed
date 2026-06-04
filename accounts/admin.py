from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Admin, Customer, Provider,
    OTPVerification, BiometricToken,
    CustomerAddress, Specialization,
    Review, PreviousWork
)


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'role', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['name', 'email']
    readonly_fields = ['created_at', 'last_login']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone_number', 'email', 'is_phone_verified', 'is_active', 'created_at']
    list_filter   = ['is_phone_verified', 'is_active']
    search_fields = ['name', 'phone_number', 'email']
    readonly_fields = ['created_at', 'last_login']


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone_number', 'specialization', 'is_approved', 'is_active', 'average_rating', 'total_reviews']
    list_filter   = ['is_approved', 'is_active', 'is_phone_verified', 'specialization']
    search_fields = ['name', 'phone_number', 'email']
    readonly_fields = ['created_at', 'last_login', 'average_rating', 'total_reviews', 'total_services']


@admin.register(OTPVerification)
class OTPAdmin(admin.ModelAdmin):
    list_display  = ['phone_number', 'user_type', 'is_used', 'attempts', 'created_at', 'expires_at']
    list_filter   = ['user_type', 'is_used']
    search_fields = ['phone_number']
    readonly_fields = ['created_at', 'expires_at']


@admin.register(BiometricToken)
class BiometricTokenAdmin(admin.ModelAdmin):
    list_display  = ['user_id', 'user_type', 'device_id', 'is_active', 'created_at', 'last_used']
    list_filter   = ['user_type', 'is_active']
    search_fields = ['user_id', 'device_id']
    readonly_fields = ['created_at', 'last_used']


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'city', 'district', 'label', 'is_default']
    list_filter   = ['city', 'is_default']
    search_fields = ['customer__name', 'city', 'district']


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display  = ['name', 'is_active', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ['get_customer', 'provider', 'rating', 'created_at']
    list_filter   = ['rating']
    search_fields = ['provider__name', 'customer__name']
    readonly_fields = ['created_at']

    def get_customer(self, obj):
        return obj.customer.name if obj.customer else "إدارة النظام"
    get_customer.short_description = 'العميل'


@admin.register(PreviousWork)
class PreviousWorkAdmin(admin.ModelAdmin):
    list_display  = ['provider', 'title', 'media_type', 'get_media_preview', 'created_at']
    list_filter   = ['media_type']
    search_fields = ['provider__name', 'title']
    readonly_fields = ['created_at', 'get_media_preview']

    def get_media_preview(self, obj):
        if obj.media_type == 'image' and obj.media_url:
            return format_html('<img src="{}" style="height:60px; border-radius:4px;" />', obj.media_url)
        elif obj.media_type == 'video' and obj.thumbnail_url:
            return format_html('<img src="{}" style="height:60px; border-radius:4px;" />', obj.thumbnail_url)
        return "—"
    get_media_preview.short_description = 'معاينة'