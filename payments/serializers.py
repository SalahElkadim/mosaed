from rest_framework import serializers
from .models import (
    PaymentRequest, OnlinePaymentAttempt, ProviderDue, DueCollectionItem,
    ProviderWallet, WalletTransaction, PayoutBatch, PayoutBatchItem,
    DueCollectionBatch,
)


class PaymentRequestSerializer(serializers.ModelSerializer):
    """لعرض نموذج الدفع — للعميل والفني"""
    request_id    = serializers.UUIDField(source='custom_request.id', read_only=True)
    request_title = serializers.CharField(source='custom_request.title', read_only=True)

    class Meta:
        model  = PaymentRequest
        fields = [
            'id', 'request_id', 'request_title',
            'amount', 'provider_share', 'platform_share',
            'payment_method', 'status',
            'created_at', 'paid_at',
        ]
        read_only_fields = fields


class PaymentMethodSelectSerializer(serializers.Serializer):
    """العميل يختار طريقة الدفع"""
    payment_method = serializers.ChoiceField(choices=PaymentRequest.METHOD_CHOICES)

    def validate(self, attrs):
        payment_request = self.context['payment_request']
        if payment_request.status != 'awaiting_method':
            raise serializers.ValidationError(
                'تم اختيار طريقة الدفع بالفعل لهذا الطلب.'
            )
        return attrs


class OnlinePaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OnlinePaymentAttempt
        fields = ['id', 'payment_url', 'status', 'created_at']
        read_only_fields = fields


class ProviderDuesStatusSerializer(serializers.ModelSerializer):
    """
    للـ endpoint المستثنى من القفل — الفني (والفلاتر) بيعرف حالته
    وقيمة المستحقات ورابط الدفع الحالي لو موجود.
    """
    current_payment_link = serializers.SerializerMethodField()

    class Meta:
        model  = ProviderDue
        fields = [
            'outstanding_amount', 'is_blocked', 'blocked_at',
            'current_payment_link',
        ]
        read_only_fields = fields

    def get_current_payment_link(self, obj):
        item = DueCollectionItem.objects.filter(
            provider=obj.provider, status='pending'
        ).order_by('-created_at').first()
        return item.payment_link if item else None


# ==================== محفظة الفني ====================

class ProviderWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProviderWallet
        fields = ['available_balance', 'total_earned', 'total_paid_out', 'updated_at']
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WalletTransaction
        fields = ['id', 'amount', 'transaction_type', 'balance_after', 'created_at']
        read_only_fields = fields


# ==================== أدمن — الباتشات الأسبوعية ====================

class PayoutBatchItemAdminSerializer(serializers.ModelSerializer):
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)

    class Meta:
        model  = PayoutBatchItem
        fields = [
            'id', 'provider_name', 'provider_phone', 'amount',
            'status', 'admin_reference_note', 'transferred_at',
        ]
        read_only_fields = fields


class PayoutBatchAdminSerializer(serializers.ModelSerializer):
    items        = PayoutBatchItemAdminSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()

    def get_total_amount(self, obj):
        return sum((item.amount for item in obj.items.all()), 0)

    class Meta:
        model  = PayoutBatch
        fields = ['id', 'week_start', 'week_end', 'status', 'total_amount', 'items', 'created_at']
        read_only_fields = fields


class DueCollectionItemAdminSerializer(serializers.ModelSerializer):
    provider_name  = serializers.CharField(source='provider.name', read_only=True)
    provider_phone = serializers.CharField(source='provider.phone_number', read_only=True)

    class Meta:
        model  = DueCollectionItem
        fields = [
            'id', 'provider_name', 'provider_phone', 'amount_due',
            'payment_link', 'status', 'paid_at',
        ]
        read_only_fields = fields


class DueCollectionBatchAdminSerializer(serializers.ModelSerializer):
    items = DueCollectionItemAdminSerializer(many=True, read_only=True)

    class Meta:
        model  = DueCollectionBatch
        fields = ['id', 'week_start', 'week_end', 'status', 'items', 'created_at']
        read_only_fields = fields


class DueCollectionItemPublicSerializer(serializers.ModelSerializer):
    """
    للعرض العام على صفحة الدفع (بدون بيانات حساسة زي رقم تليفون الفني)
    """
    class Meta:
        model  = DueCollectionItem
        fields = ['id', 'amount_due', 'status', 'created_at', 'paid_at']
        read_only_fields = fields