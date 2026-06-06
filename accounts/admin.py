# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg, Count

from .models import (
    Admin, Customer, Provider,
    OTPVerification, BiometricToken,
    CustomerAddress, ProviderAddress,
    City, Region, Specialization,
    Review, PreviousWork,
)


# ==================== INLINES ====================

class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0
    readonly_fields = ['id', 'created_at']
    fields = ['city', 'region', 'district', 'street', 'building_no',
              'floor_no', 'apartment_no', 'label', 'is_default']


class ProviderAddressInline(admin.TabularInline):
    model = ProviderAddress
    extra = 0
    readonly_fields = ['id', 'created_at']
    fields = ['city', 'region', 'district', 'street', 'building_no', 'label', 'is_default']


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ['id', 'customer', 'rating', 'comment', 'created_at']
    can_delete = True


class PreviousWorkInline(admin.TabularInline):
    model = PreviousWork
    extra = 0
    readonly_fields = ['id', 'media_type', 'media_url', 'thumbnail_url', 'created_at']
    fields = ['title', 'description', 'media_type', 'media_url', 'thumbnail_url']


class RegionInline(admin.TabularInline):
    model = Region
    extra = 0
    fields = ['name', 'is_active']


# ==================== ADMIN ====================

@admin.register(Admin)
class AdminAdmin(UserAdmin):
    list_display  = ['name', 'email', 'phone_number', 'role', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['name', 'email', 'phone_number']
    ordering      = ['-created_at']
    readonly_fields = ['id', 'created_at', 'last_login']

    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        (_('Personal Info'), {'fields': ('name', 'phone_number')}),
        (_('Role & Permissions'), {
            'fields': ('role', 'created_by', 'custom_permissions',
                       'is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions')
        }),
        (_('Dates'), {'fields': ('created_at', 'last_login')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'phone_number', 'role', 'password1', 'password2'),
        }),
    )


# ==================== CUSTOMER ====================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display    = ['name', 'phone_number', 'email', 'is_phone_verified',
                       'is_active', 'created_at']
    list_filter     = ['is_active', 'is_phone_verified']
    search_fields   = ['name', 'phone_number', 'email']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at', 'last_login']
    inlines         = [CustomerAddressInline]

    fieldsets = (
        (None,               {'fields': ('id', 'name', 'phone_number', 'email')}),
        (_('Status'),        {'fields': ('is_active', 'is_phone_verified')}),
        (_('Device'),        {'fields': ('device_token',)}),
        (_('Dates'),         {'fields': ('created_at', 'last_login')}),
    )

    actions = ['activate_customers', 'deactivate_customers']

    @admin.action(description='Activate selected customers')
    def activate_customers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} customer(s) activated.')

    @admin.action(description='Deactivate selected customers')
    def deactivate_customers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} customer(s) deactivated.')


# ==================== PROVIDER ====================

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone_number', 'specialization', 'is_phone_verified',
                     'is_approved', 'is_active', 'average_rating', 'total_reviews', 'created_at']
    list_filter   = ['is_active', 'is_approved', 'is_phone_verified', 'specialization']
    search_fields = ['name', 'phone_number', 'email', 'national_id']
    ordering      = ['-created_at']
    readonly_fields = ['id', 'created_at', 'last_login',
                       'average_rating', 'total_reviews', 'total_services', 'wallet_balance']
    inlines       = [ProviderAddressInline, PreviousWorkInline, ReviewInline]

    fieldsets = (
        (None,                  {'fields': ('id', 'name', 'phone_number', 'email')}),
        (_('Professional Info'), {'fields': ('specialization', 'national_id',
                                             'commercial_registration', 'contract_image')}),
        (_('Status'),           {'fields': ('is_active', 'is_approved', 'is_phone_verified')}),
        (_('Stats'),            {'fields': ('wallet_balance', 'total_services',
                                            'average_rating', 'total_reviews')}),
        (_('Device'),           {'fields': ('device_token',)}),
        (_('Dates'),            {'fields': ('created_at', 'last_login')}),
    )

    actions = ['approve_providers', 'block_providers', 'unblock_providers']

    @admin.action(description='Approve selected providers')
    def approve_providers(self, request, queryset):
        updated = queryset.filter(is_phone_verified=True).update(is_approved=True)
        self.message_user(request, f'{updated} provider(s) approved.')

    @admin.action(description='Block selected providers')
    def block_providers(self, request, queryset):
        updated = queryset.update(is_active=False, is_approved=False)
        self.message_user(request, f'{updated} provider(s) blocked.')

    @admin.action(description='Unblock selected providers')
    def unblock_providers(self, request, queryset):
        updated = queryset.update(is_active=True, is_approved=True)
        self.message_user(request, f'{updated} provider(s) unblocked.')


# ==================== SPECIALIZATION ====================

@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display    = ['name', 'providers_count', 'is_active', 'created_at']
    list_filter     = ['is_active']
    search_fields   = ['name']
    ordering        = ['name']
    readonly_fields = ['id', 'created_at']

    def providers_count(self, obj):
        return obj.providers.count()
    providers_count.short_description = 'Providers'


# ==================== CITY & REGION ====================

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display    = ['name', 'regions_count', 'is_active', 'created_at']
    list_filter     = ['is_active']
    search_fields   = ['name']
    ordering        = ['name']
    readonly_fields = ['id', 'created_at']
    inlines         = [RegionInline]

    def regions_count(self, obj):
        return obj.regions.count()
    regions_count.short_description = 'Regions'


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display    = ['name', 'city', 'is_active', 'created_at']
    list_filter     = ['is_active', 'city']
    search_fields   = ['name', 'city__name']
    ordering        = ['city__name', 'name']
    readonly_fields = ['id', 'created_at']


# ==================== OTP ====================

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display    = ['phone_number', 'user_type', 'is_used', 'attempts',
                       'created_at', 'expires_at', 'status_badge']
    list_filter     = ['user_type', 'is_used']
    search_fields   = ['phone_number']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at', 'expires_at']

    def status_badge(self, obj):
        if obj.is_used:
            color, label = '#888', 'Used'
        elif obj.is_expired():
            color, label = '#e74c3c', 'Expired'
        else:
            color, label = '#27ae60', 'Valid'
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>', color, label
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # OTPs يتعملوا برمجياً بس


# ==================== BIOMETRIC ====================

@admin.register(BiometricToken)
class BiometricTokenAdmin(admin.ModelAdmin):
    list_display    = ['user_id', 'user_type', 'device_id', 'is_active',
                       'created_at', 'last_used', 'expires_at']
    list_filter     = ['user_type', 'is_active']
    search_fields   = ['user_id', 'device_id']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'token', 'created_at', 'expires_at', 'last_used']

    actions = ['revoke_tokens']

    @admin.action(description='Revoke selected biometric tokens')
    def revoke_tokens(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} token(s) revoked.')


# ==================== REVIEWS ====================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display    = ['customer', 'provider', 'rating', 'comment_preview', 'created_at']
    list_filter     = ['rating']
    search_fields   = ['customer__name', 'provider__name', 'comment']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at']

    def comment_preview(self, obj):
        return (obj.comment[:60] + '…') if len(obj.comment) > 60 else obj.comment
    comment_preview.short_description = 'Comment'


# ==================== PREVIOUS WORKS ====================

@admin.register(PreviousWork)
class PreviousWorkAdmin(admin.ModelAdmin):
    list_display    = ['provider', 'title', 'media_type', 'media_link', 'created_at']
    list_filter     = ['media_type']
    search_fields   = ['provider__name', 'title']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at']

    def media_link(self, obj):
        if obj.media_url:
            return format_html('<a href="{}" target="_blank">View</a>', obj.media_url)
        return '—'
    media_link.short_description = 'Media'


# ==================== ADDRESSES ====================

@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display    = ['customer', 'city', 'region', 'district', 'is_default', 'created_at']
    list_filter     = ['city', 'is_default']
    search_fields   = ['customer__name', 'district', 'street']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at']


@admin.register(ProviderAddress)
class ProviderAddressAdmin(admin.ModelAdmin):
    list_display    = ['provider', 'city', 'region', 'district', 'is_default', 'created_at']
    list_filter     = ['city', 'is_default']
    search_fields   = ['provider__name', 'district', 'street']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at']