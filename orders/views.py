from decimal import Decimal

from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Cart, CartItem, Order, OrderItem,
    Shipment, Payment, Commission, Payout, PayoutItem,
)
from .serializers import (
    CartSerializer, CartItemSerializer,
    OrderSerializer, OrderItemSerializer,
    CheckoutSerializer,
    ShipmentSerializer, PaymentSerializer,
    CommissionSerializer, PayoutSerializer,
    _resolve_vendor,
)


class CartViewSet(viewsets.GenericViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def _get_or_create_cart(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def list(self, request, *args, **kwargs):
        cart = self._get_or_create_cart()
        return Response(self.get_serializer(cart).data)

    @action(detail=False, methods=['delete'], url_path='clear')
    def clear(self, request):
        cart = self._get_or_create_cart()
        cart.items.all().delete()
        return Response({"detail": "Cart cleared."}, status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return (
            CartItem.objects
            .select_related('cart', 'product_variant')
            .filter(cart__user=self.request.user)
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        variant  = serializer.validated_data['product_variant']
        quantity = serializer.validated_data['quantity']

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_variant=variant,
            defaults={'quantity': quantity},
        )

        if not created:
            new_qty = item.quantity + quantity
            if hasattr(variant, 'stock') and new_qty > variant.stock:
                return Response(
                    {"quantity": f"Only {variant.stock} unit(s) available."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.quantity = new_qty
            item.save(update_fields=['quantity'])

        out = self.get_serializer(item)
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return (
            Order.objects
            .select_related('user', 'shipping_address')
            .prefetch_related(
                'items__product_variant',
                'items__vendor',
                'items__commission',
            )
            .filter(user=self.request.user)
        )

    @action(detail=False, methods=['post'], url_path='checkout')
    @transaction.atomic
    def checkout(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        cart: Cart        = serializer.validated_data['cart']
        shipping_address  = serializer.validated_data['shipping_address']

        cart_items   = list(cart.items.select_related('product_variant').all())
        subtotal     = sum(i.quantity * i.product_variant.price for i in cart_items)
        shipping_fee = self._calculate_shipping_fee(cart_items)
        total        = subtotal + shipping_fee

        order = Order.objects.create(
            user=request.user,
            shipping_address=shipping_address,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total_amount=total,
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.UNPAID,
        )

        for cart_item in cart_items:
            variant    = cart_item.product_variant
            unit_price = variant.price
            line_total = unit_price * cart_item.quantity
            vendor     = _resolve_vendor(variant)  

            order_item = OrderItem.objects.create(
                order=order,
                product_variant=variant,
                vendor=vendor,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
                status=OrderItem.Status.PENDING,
            )
            rate              = vendor.commission_rate                      
            commission_amount = (line_total * rate / Decimal('100')).quantize(Decimal('0.01'))
            net_amount        = line_total - commission_amount

            Commission.objects.create(
                vendor=vendor,
                order_item=order_item,
                gross_amount=line_total,
                commission_rate=rate,
                commission_amount=commission_amount,
                net_amount=net_amount,
                status=Commission.Status.PENDING,
            )
            if hasattr(variant, 'stock'):
                variant.stock -= cart_item.quantity
                variant.save(update_fields=['stock'])

        cart.items.all().delete()

        return Response(
            OrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status not in (Order.Status.PENDING, Order.Status.CONFIRMED):
            return Response(
                {"detail": "Only pending or confirmed orders can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in order.items.select_related('product_variant').all():
            variant = item.product_variant
            if hasattr(variant, 'stock'):
                variant.stock += item.quantity
                variant.save(update_fields=['stock'])

            item.status = OrderItem.Status.CANCELLED
            item.save(update_fields=['status'])
            if hasattr(item, 'commission'):
                item.commission.status = Commission.Status.PENDING
                item.commission.save(update_fields=['status'])

        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])

        return Response(OrderSerializer(order, context={'request': request}).data)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /orders/checkout/ to place an order."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": "Only pending orders can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed = {'shipping_address'}
        data    = {k: v for k, v in request.data.items() if k in allowed}

        serializer = self.get_serializer(order, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(self.get_serializer(order).data)

    @staticmethod
    def _calculate_shipping_fee(cart_items) -> Decimal:
        seen_vendors = set()
        total_fee    = Decimal('0')

        for item in cart_items:
            vendor = _resolve_vendor(item.product_variant)
            if vendor is None or vendor.id in seen_vendors:
                continue
            seen_vendors.add(vendor.id)
            fee = getattr(vendor, 'shipping_fee', Decimal('0')) or Decimal('0')
            total_fee += fee

        return total_fee


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            OrderItem.objects
            .select_related('order', 'product_variant', 'vendor')
            .prefetch_related('commission')
            .filter(order__user=self.request.user)
        )

class ShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Shipment.objects.filter(
            order_item__order__user=self.request.user
        ).select_related('order_item')


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(
            order__user=self.request.user
        ).select_related('order')



class CommissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Commission.objects
            .select_related('vendor', 'order_item')
            .filter(vendor__user=self.request.user)
        )


class PayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Payout.objects
            .select_related('vendor')
            .prefetch_related('items__commission')
            .filter(vendor__user=self.request.user)
        )