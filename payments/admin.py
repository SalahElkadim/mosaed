from django.contrib import admin
from .models import (
    PaymentRequest, OnlinePaymentAttempt,
    ProviderWallet, WalletTransaction,
    ProviderDue, DueTransaction,
    PayoutBatch, PayoutBatchItem,
    DueCollectionBatch, DueCollectionItem,
)


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'provider_share', 'platform_share', 'payment_method', 'status', 'created_at', 'paid_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('id',)
    readonly_fields = [f.name for f in PaymentRequest._meta.fields]


@admin.register(OnlinePaymentAttempt)
class OnlinePaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment_request', 'moyasar_payment_id', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('moyasar_payment_id',)


@admin.register(ProviderWallet)
class ProviderWalletAdmin(admin.ModelAdmin):
    list_display = ('provider', 'available_balance', 'total_earned', 'total_paid_out', 'updated_at')
    search_fields = ('provider__name', 'provider__phone_number')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'amount', 'transaction_type', 'balance_after', 'created_at')
    list_filter = ('transaction_type',)


@admin.register(ProviderDue)
class ProviderDueAdmin(admin.ModelAdmin):
    list_display = ('provider', 'outstanding_amount', 'total_charged', 'total_paid', 'is_blocked', 'blocked_at')
    list_filter = ('is_blocked',)
    search_fields = ('provider__name', 'provider__phone_number')


@admin.register(DueTransaction)
class DueTransactionAdmin(admin.ModelAdmin):
    list_display = ('due', 'amount', 'transaction_type', 'balance_after', 'created_at')
    list_filter = ('transaction_type',)


class PayoutBatchItemInline(admin.TabularInline):
    model = PayoutBatchItem
    extra = 0
    readonly_fields = ('provider', 'amount', 'status', 'transferred_at', 'admin_reference_note')
    can_delete = False


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'week_start', 'week_end', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [PayoutBatchItemInline]


class DueCollectionItemInline(admin.TabularInline):
    model = DueCollectionItem
    extra = 0
    readonly_fields = ('provider', 'amount_due', 'payment_link', 'status', 'paid_at')
    can_delete = False


@admin.register(DueCollectionBatch)
class DueCollectionBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'week_start', 'week_end', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [DueCollectionItemInline]
