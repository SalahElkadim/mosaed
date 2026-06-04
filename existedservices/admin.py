from django.contrib import admin
from .models import ExistedService, ServiceAttribute, Booking, BookingItem


# ==================== SERVICE ====================

class ServiceAttributeInline(admin.TabularInline):
    model  = ServiceAttribute
    extra  = 1
    fields = ['name', 'details', 'unit_cost']


@admin.register(ExistedService)
class ExistedServiceAdmin(admin.ModelAdmin):
    list_display   = ['title', 'date', 'is_active', 'created_at']
    list_filter    = ['is_active']
    search_fields  = ['title']
    inlines        = [ServiceAttributeInline]


@admin.register(ServiceAttribute)
class ServiceAttributeAdmin(admin.ModelAdmin):
    list_display  = ['name', 'service', 'unit_cost', 'created_at']
    list_filter   = ['service']
    search_fields = ['name', 'service__title']


# ==================== BOOKING ====================

class BookingItemInline(admin.TabularInline):
    model           = BookingItem
    extra           = 0
    fields          = ['attribute', 'value', 'unit_cost_snapshot', 'cost']
    readonly_fields = ['unit_cost_snapshot', 'cost']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display    = ['id', 'customer', 'service', 'status', 'total_cost', 'scheduled_date', 'created_at']
    list_filter     = ['status', 'service']
    search_fields   = ['customer__name', 'customer__phone_number', 'service__title']
    readonly_fields = ['total_cost', 'created_at', 'updated_at']
    inlines         = [BookingItemInline]


@admin.register(BookingItem)
class BookingItemAdmin(admin.ModelAdmin):
    list_display    = ['booking', 'attribute', 'value', 'unit_cost_snapshot', 'cost']
    readonly_fields = ['unit_cost_snapshot', 'cost']