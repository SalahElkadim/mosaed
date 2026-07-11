from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PlatformSettings,
    CustomRequest,
    ServiceOffer,
    RequestChat,
    Notification,
    DeviceToken,
)


# ==================== PLATFORM SETTINGS ====================

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display  = ['key', 'value', 'updated_at']
    search_fields = ['key']
    ordering      = ['key']


# ==================== SERVICE OFFER (Inline) ====================

class ServiceOfferInline(admin.TabularInline):
    model = ServiceOffer
    extra = 0
    fields = ['provider', 'provider_price', 'platform_fee', 'final_price', 'status', 'created_at']
    readonly_fields = ['platform_fee', 'final_price', 'created_at']
    show_change_link = True


# ==================== CUSTOM REQUEST ====================

@admin.register(CustomRequest)
class CustomRequestAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'customer', 'specialization', 'status',
        'scheduled_date', 'accepted_provider', 'offers_count',
        'expires_at', 'created_at',
    ]
    list_filter   = ['status', 'specialization', 'scheduled_date', 'created_at']
    search_fields = [
        'title', 'description',
        'customer__name', 'customer__phone_number',
        'accepted_provider__name',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'expires_at']
    autocomplete_fields = ['customer', 'specialization', 'address', 'accepted_provider']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    inlines = [ServiceOfferInline]

    fieldsets = (
        ('البيانات الأساسية', {
            'fields': ('id', 'customer', 'specialization', 'title', 'description', 'image')
        }),
        ('العنوان والموعد', {
            'fields': ('address', 'scheduled_date')
        }),
        ('الحالة', {
            'fields': ('status', 'accepted_provider', 'expires_at')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def offers_count(self, obj):
        return obj.offers.count()
    offers_count.short_description = 'عدد العروض'


# ==================== SERVICE OFFER ====================

@admin.register(ServiceOffer)
class ServiceOfferAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'request', 'provider', 'provider_price',
        'platform_fee', 'final_price', 'status', 'created_at',
    ]
    list_filter   = ['status', 'created_at']
    search_fields = [
        'request__title', 'provider__name', 'provider__phone_number',
    ]
    readonly_fields = ['id', 'platform_fee', 'final_price', 'created_at', 'updated_at']
    autocomplete_fields = ['request', 'provider']
    ordering = ['-created_at']


# ==================== REQUEST CHAT ====================

@admin.register(RequestChat)
class RequestChatAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'request', 'sender_type', 'sender_id',
        'short_message', 'is_read', 'read_at', 'created_at',
    ]
    list_filter   = ['sender_type', 'is_read', 'created_at']
    search_fields = ['request__title', 'message', 'sender_id']
    readonly_fields = ['id', 'created_at']
    autocomplete_fields = ['request']
    ordering = ['-created_at']

    def short_message(self, obj):
        return (obj.message[:50] + '…') if len(obj.message) > 50 else obj.message
    short_message.short_description = 'الرسالة'


# ==================== NOTIFICATION ====================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'recipient_type', 'recipient_id', 'event',
        'title', 'is_read', 'created_at', 'read_at',
    ]
    list_filter   = ['recipient_type', 'event', 'is_read', 'created_at']
    search_fields = ['recipient_id', 'title', 'body']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


# ==================== DEVICE TOKEN ====================

@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'recipient_type', 'recipient_id',
        'short_token', 'created_at', 'updated_at',
    ]
    list_filter   = ['recipient_type', 'created_at']
    search_fields = ['recipient_id', 'token']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def short_token(self, obj):
        return f"{obj.token[:25]}..." if len(obj.token) > 25 else obj.token
    short_token.short_description = 'Token'