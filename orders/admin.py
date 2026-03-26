from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, Shipment, Payment, Commission, Payout, PayoutItem

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
    search_fields = ('user__username',)
    list_filter = ('status', 'payment_status')
    readonly_fields = ('subtotal', 'total_amount')
    inlines = [OrderItemInline]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'tracking_number', 'carrier', 'shipped_at', 'delivered_at')
    search_fields = ('order_item__order__user__username', 'tracking_number')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'gateway', 'amount', 'status', 'created_at')
    search_fields = ('order__user__username', 'payment_intent_id')
    list_filter = ('status', 'gateway')


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'order_item', 'gross_amount', 'commission_rate', 'commission_amount', 'net_amount', 'status')
    search_fields = ('vendor__company_name', 'order_item__order__user__username')
    list_filter = ('status',)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'amount', 'status', 'payout_method', 'initiated_at', 'completed_at')
    search_fields = ('vendor__company_name',)
    list_filter = ('status',)
    inlines = [PayoutItemInline]
