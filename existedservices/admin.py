from django.contrib import admin

from .models import (
    ExistedService,
    Warranty,
    ServiceAttribute,
    Booking,
    BookingItem,
    ServiceReview,
    ServiceProvider,
    ServiceCompletionForm,
    CompletionMedia,
    Coupon,
    PreviousWork,
)


class WarrantyInline(admin.StackedInline):
    model = Warranty
    extra = 0


class ServiceAttributeInline(admin.TabularInline):
    model = ServiceAttribute
    extra = 0


class ServiceProviderInline(admin.TabularInline):
    model = ServiceProvider
    extra = 0


class BookingItemInline(admin.TabularInline):
    model = BookingItem
    extra = 0


class CompletionMediaInline(admin.TabularInline):
    model = CompletionMedia
    extra = 0


# =======================
# Existed Service
# =======================

@admin.register(ExistedService)
class ExistedServiceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "specialization",
        "visit_cost",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
        "specialization",
        "created_at",
    )
    search_fields = (
        "title",
        "details",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = [
        WarrantyInline,
        ServiceAttributeInline,
        ServiceProviderInline,
    ]


# =======================
# Warranty
# =======================

@admin.register(Warranty)
class WarrantyAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "duration_value",
        "duration_type",
    )
    search_fields = (
        "service__title",
    )


# =======================
# Service Attribute
# =======================

@admin.register(ServiceAttribute)
class ServiceAttributeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service",
        "unit_name",
        "quantity_name",
        "unit_cost",
    )
    list_filter = ("service",)
    search_fields = (
        "name",
        "service__title",
    )


# =======================
# Booking
# =======================

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "service",
        "provider",
        "scheduled_date",
        "status",
        "final_cost",
    )
    list_filter = (
        "status",
        "scheduled_date",
        "service",
    )
    search_fields = (
        "customer__name",
        "service__title",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = [BookingItemInline]


# =======================
# Booking Item
# =======================

@admin.register(BookingItem)
class BookingItemAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "attribute",
        "value",
        "unit_cost_snapshot",
        "cost",
    )
    search_fields = (
        "booking__id",
        "attribute__name",
    )


# =======================
# Reviews
# =======================

@admin.register(ServiceReview)
class ServiceReviewAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "customer",
        "stars",
        "created_at",
    )
    list_filter = (
        "stars",
        "created_at",
    )
    search_fields = (
        "service__title",
        "customer__name",
    )


# =======================
# Providers
# =======================

@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "provider",
        "is_available",
        "created_at",
    )
    list_filter = (
        "is_available",
        "service",
    )
    search_fields = (
        "service__title",
        "provider__name",
    )


# =======================
# Completion Form
# =======================

@admin.register(ServiceCompletionForm)
class ServiceCompletionFormAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "status",
        "is_finished",
        "started_at",
        "finished_at",
    )
    list_filter = (
        "status",
        "is_finished",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = [CompletionMediaInline]


# =======================
# Completion Media
# =======================

@admin.register(CompletionMedia)
class CompletionMediaAdmin(admin.ModelAdmin):
    list_display = (
        "form",
        "media_type",
        "created_at",
    )
    list_filter = ("media_type",)


# =======================
# Coupon
# =======================

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "service",
        "used_count",
        "is_active",
        "valid_until",
    )
    list_filter = (
        "discount_type",
        "is_active",
    )
    search_fields = (
        "code",
        "service__title",
    )


# =======================
# Previous Work
# =======================

@admin.register(PreviousWork)
class PreviousWorkAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "completion_form",
        "created_at",
    )
    list_filter = ("service",)