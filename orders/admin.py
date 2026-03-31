from django.contrib import admin
from django.utils import timezone

from .models import (
    Cart, CartItem, Commission, Order, OrderItem,
    Payment, Payout, PayoutItem, Shipment,
)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ('product_variant', 'quantity', 'created_at')
    readonly_fields = ('created_at',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product_variant', 'vendor', 'quantity', 'unit_price', 'line_total', 'status')
    readonly_fields = ('unit_price', 'line_total')


class PayoutItemInline(admin.TabularInline):
    model = PayoutItem
    extra = 0
    fields = ('commission', 'amount')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username',)
    inlines = [CartItemInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_status', 'total_amount', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('status', 'payment_status')
    readonly_fields = ('subtotal', 'shipping_fee', 'total_amount', 'payment_status', 'created_at', 'updated_at')
    inlines = [OrderItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'shipping_address')


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'tracking_number', 'carrier', 'shipped_at', 'delivered_at')
    search_fields = ('order_item__order__user__username', 'tracking_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'gateway', 'amount', 'status', 'payment_intent_id', 'created_at')
    search_fields = ('order__user__username', 'payment_intent_id')
    list_filter = ('status', 'gateway')
    readonly_fields = ('payment_intent_id', 'status', 'created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order__user')


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = (
        'vendor', 'order_item', 'gross_amount',
        'commission_rate', 'commission_amount', 'net_amount', 'status',
    )
    search_fields = ('vendor__company_name', 'order_item__order__user__username')
    list_filter = ('status',)
    readonly_fields = (
        'vendor', 'order_item', 'gross_amount',
        'commission_rate', 'commission_amount', 'net_amount',
        'created_at', 'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor', 'order_item__order__user')


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'amount', 'status', 'payout_method', 'initiated_at', 'completed_at')
    search_fields = ('vendor__company_name',)
    list_filter = ('status',)
    readonly_fields = ('amount', 'payout_intent_id', 'initiated_at', 'completed_at', 'created_at', 'updated_at')
    inlines = [PayoutItemInline]
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected payouts as completed')
    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status=Payout.Status.PROCESSING).update(
            status=Payout.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        self.message_user(request, f'{updated} payout(s) marked as completed.')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor')