from decimal import Decimal
from rest_framework import serializers
from accounts.models import Address
from .models import (
    Cart, CartItem, Order, OrderItem,
    Shipment, Payment, Commission, Payout, PayoutItem,
)
from accounts.serializers import AddressSerializer


def _resolve_vendor(variant):
    try:
        return variant.product.vendor.vendor_profile
    except AttributeError:
        return None



class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source='product_variant.variant_name', read_only=True
    )
    unit_price = serializers.DecimalField(
        source='product_variant.price', max_digits=10, decimal_places=2, read_only=True
    )
    line_total = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'product_variant', 'product_name',
            'quantity', 'unit_price', 'line_total',
            'thumbnail',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_thumbnail(self, obj) -> str | None:
        product = obj.product_variant.product

        # Prefer the primary image, fall back to first by display_order
        image_obj = (
            product.images.filter(is_primary=True).first()
            or product.images.first()
        )

        if not image_obj or not image_obj.image_url:
            return None

        request = self.context.get('request')
        return (
            request.build_absolute_uri(image_obj.image_url.url)
            if request
            else image_obj.image_url.url
        )

    def get_line_total(self, obj) -> Decimal:
        return obj.quantity * obj.product_variant.price

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate_product_variant(self, variant):
        if hasattr(variant, 'stock') and variant.stock < 1:
            raise serializers.ValidationError(
                f"'{variant.variant_name}' is out of stock."
            )
        return variant

    def validate(self, attrs):
        variant = attrs.get('product_variant', getattr(self.instance, 'product_variant', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', 1))
        if hasattr(variant, 'stock') and quantity > variant.stock:
            raise serializers.ValidationError(
                {"quantity": f"Only {variant.stock} unit(s) available in stock."}
            )
        return attrs


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    cart_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id', 'user', 'items',
            'total_items', 'cart_total',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_total_items(self, obj) -> int:
        return sum(item.quantity for item in obj.items.all())

    def get_cart_total(self, obj) -> Decimal:
        return sum(item.quantity * item.product_variant.price for item in obj.items.all())


class CommissionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)

    class Meta:
        model = Commission
        fields = [
            'id', 'vendor', 'vendor_name', 'order_item',
            'gross_amount', 'commission_rate',
            'commission_amount', 'net_amount',
            'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source='product_variant.variant_name', read_only=True
    )
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    commission = CommissionSerializer(read_only=True)
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_variant', 'product_name', 'thumbnail',
            'vendor', 'vendor_name',
            'quantity', 'unit_price', 'line_total',
            'status', 'commission',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'unit_price', 'line_total',
            'vendor', 'created_at', 'updated_at',
        ]
    
    def get_thumbnail(self, obj) -> str | None:
        product = obj.product_variant.product
        image_obj = (
            product.images.filter(is_primary=True).first()
            or product.images.first()
        )

        if not image_obj or not image_obj.image_url:
            return None

        request = self.context.get('request')
        return (
            request.build_absolute_uri(image_obj.image_url.url)
            if request
            else image_obj.image_url.url
        )

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    shipping_address = AddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_email',
            'shipping_address',
            'status', 'payment_status',
            'subtotal', 'shipping_fee', 'total_amount',
            'items', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user',
            'subtotal', 'shipping_fee', 'total_amount',
            'payment_status',
            'created_at', 'updated_at',
        ]

    def validate_shipping_address(self, address):
        request = self.context.get('request')
        if request and address.user_id != request.user.id:
            raise serializers.ValidationError("This address does not belong to you.")
        return address


class CheckoutSerializer(serializers.Serializer):
    shipping_address = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all()
    )

    def validate_shipping_address(self, address):
        if address.user_id != self.context['request'].user.id:
            raise serializers.ValidationError("This address does not belong to you.")
        return address

    def validate(self, attrs):
        user = self.context['request'].user

        try:
            cart = (
                Cart.objects
                .prefetch_related('items__product_variant')
                .get(user=user)
            )
        except Cart.DoesNotExist:
            raise serializers.ValidationError("You don't have an active cart.")

        if not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty.")

        errors = []
        for item in cart.items.all():
            variant = item.product_variant
            vendor = _resolve_vendor(variant)

            if vendor is None:
                errors.append(f"'{variant.variant_name}' has no associated vendor.")
                continue

            if not vendor.is_approved:
                errors.append(
                    f"Vendor '{vendor.company_name}' is not approved and cannot accept orders."
                )

            if hasattr(variant, 'stock') and item.quantity > variant.stock:
                errors.append(
                    f"Insufficient stock for '{variant.variant_name}'. "
                    f"Available: {variant.stock}."
                )

        if errors:
            raise serializers.ValidationError(errors)

        attrs['cart'] = cart
        return attrs


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class PayoutItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayoutSerializer(serializers.ModelSerializer):
    items = PayoutItemSerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)

    class Meta:
        model = Payout
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']