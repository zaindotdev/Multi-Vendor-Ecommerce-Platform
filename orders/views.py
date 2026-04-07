from __future__ import annotations

from django.http import HttpResponse
import stripe
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.views import View

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import VendorProfile
from products.models import ProductVariant

from .models import (
    Cart, CartItem, Commission, Order, OrderItem,
    Payment, Payout, PayoutItem, Shipment,
)
from .serializers import (
    CartItemSerializer, CartSerializer,
    CheckoutSerializer, CommissionSerializer,
    OrderItemSerializer, OrderSerializer,
    PaymentSerializer, PayoutSerializer,
    ShipmentSerializer, _resolve_vendor,
)
from .tasks import (
    send_order_confirmation_email,
    send_vendor_new_order_notification,
    send_order_status_update_email,
    send_order_cancelled_email,
    process_stripe_refund,
)

stripe.api_key = settings.STRIPE_SECRET_KEY

ALLOWED_BUYER_CANCELLATION_STATUSES = {Order.Status.PENDING, Order.Status.CONFIRMED}

VENDOR_STATUS_TRANSITIONS: dict[str, set[str]] = {
    Order.Status.PENDING:    {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED:  {Order.Status.SHIPPED},
    Order.Status.SHIPPED:    {Order.Status.DELIVERED},
    Order.Status.DELIVERED:  set(),
    Order.Status.CANCELLED:  set(),
    Order.Status.REFUNDED:   set(),
}


class CartViewSet(viewsets.GenericViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def _get_or_create_cart(self) -> Cart:
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def list(self, request: Request, *args, **kwargs) -> Response:
        cart = self._get_or_create_cart()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'], url_path='clear')
    def clear(self, request: Request) -> Response:
        cart = self._get_or_create_cart()
        cart.items.all().delete()
        return Response({'detail': 'Cart cleared.'}, status=status.HTTP_204_NO_CONTENT)


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

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        variant = serializer.validated_data['product_variant']
        quantity = serializer.validated_data['quantity']

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_variant=variant,
            defaults={'quantity': quantity},
        )

        if not created:
            new_qty = item.quantity + quantity
            if new_qty > variant.stock:
                return Response(
                    {'quantity': f'Only {variant.stock} unit(s) available.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.quantity = new_qty
            item.save(update_fields=['quantity'])

        return Response(
            self.get_serializer(item).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        item = self.get_object()
        serializer = self.get_serializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self.get_serializer(item).data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = (
            Order.objects
            .select_related('user', 'shipping_address')
            .prefetch_related(
                'items__product_variant__product',
                'items__vendor',
                'items__commission',
                'payment',
            )
        )

        if role == 'admin':
            return qs.all()

        if role == 'vendor':
            try:
                vendor_profile = user.vendor_profile
            except VendorProfile.DoesNotExist:
                return qs.none()
            return qs.filter(items__vendor=vendor_profile).distinct()

        return qs.filter(user=user)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request: Request) -> Response:
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            cart: Cart = serializer.validated_data['cart']
            shipping_address = serializer.validated_data['shipping_address']

            cart_items = list(
                cart.items
                .select_related('product_variant__product__vendor__vendor_profile')
                .all()
            )

            subtotal = sum(i.quantity * i.product_variant.price for i in cart_items)
            shipping_fee = self._calculate_shipping_fee(cart_items)
            total = subtotal + shipping_fee

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
                variant = cart_item.product_variant

                # Atomic stock decrement — prevents race conditions.
                updated = (
                    ProductVariant.objects
                    .filter(pk=variant.pk, stock__gte=cart_item.quantity)
                    .update(stock=F('stock') - cart_item.quantity)
                )
                if not updated:
                    raise transaction.TransactionManagementError(
                        f"Insufficient stock for '{variant.variant_name}'. Please update your cart."
                    )

                vendor = _resolve_vendor(variant)
                unit_price = variant.price
                line_total = unit_price * cart_item.quantity

                order_item = OrderItem.objects.create(
                    order=order,
                    product_variant=variant,
                    vendor=vendor,
                    quantity=cart_item.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    status=OrderItem.Status.PENDING,
                )

                rate = vendor.commission_rate
                commission_amount = (line_total * rate / Decimal('100')).quantize(Decimal('0.01'))
                net_amount = line_total - commission_amount

                Commission.objects.create(
                    vendor=vendor,
                    order_item=order_item,
                    gross_amount=line_total,
                    commission_rate=rate,
                    commission_amount=commission_amount,
                    net_amount=net_amount,
                    status=Commission.Status.PENDING,
                )

            cart.items.all().delete()

        # Tasks run after the transaction commits — order is fully persisted by this point.
        send_order_confirmation_email.delay(order.id)

        vendor_ids = list(
            OrderItem.objects
            .filter(order=order)
            .values_list('vendor_id', flat=True)
            .distinct()
        )
        for vendor_id in vendor_ids:
            send_vendor_new_order_notification.delay(order.id, vendor_id)

        return Response(
            OrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request: Request, pk=None) -> Response:
        order = self.get_object()

        if order.status not in ALLOWED_BUYER_CANCELLATION_STATUSES:
            return Response(
                {'detail': 'Only pending or confirmed orders can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in order.items.select_related('product_variant').all():
                ProductVariant.objects.filter(pk=item.product_variant_id).update(
                    stock=F('stock') + item.quantity
                )
                item.status = OrderItem.Status.CANCELLED
                item.save(update_fields=['status'])

                commission = getattr(item, 'commission', None)
                if commission:
                    commission.status = Commission.Status.PENDING
                    commission.save(update_fields=['status'])

            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])

        send_order_cancelled_email.delay(order.id)

        payment = getattr(order, 'payment', None)
        if payment and payment.status == Payment.Status.PAID:
            process_stripe_refund.delay(order.id)

        return Response(OrderSerializer(order, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request: Request, pk=None) -> Response:
        order = self.get_object()
        user = request.user
        role = getattr(user, 'role', None)

        new_status = request.data.get('status')
        if not new_status:
            return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        allowed_next = VENDOR_STATUS_TRANSITIONS.get(order.status, set())
        if new_status not in allowed_next:
            return Response(
                {'detail': f"Cannot transition from '{order.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role == 'vendor':
            try:
                vendor_profile = user.vendor_profile
            except VendorProfile.DoesNotExist:
                return Response({'detail': 'Vendor profile not found.'}, status=status.HTTP_403_FORBIDDEN)

            owns_any_item = order.items.filter(vendor=vendor_profile).exists()
            if not owns_any_item:
                return Response({'detail': 'You do not have items in this order.'}, status=status.HTTP_403_FORBIDDEN)

        elif role != 'admin':
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        order.status = new_status
        order.save(update_fields=['status'])

        send_order_status_update_email.delay(order.id)

        return Response(OrderSerializer(order, context={'request': request}).data)

    def create(self, request: Request, *args, **kwargs) -> Response:
        return Response(
            {'detail': 'Use POST /orders/checkout/ to place an order.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {'detail': 'Only pending orders can be edited.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed = {'shipping_address'}
        data = {k: v for k, v in request.data.items() if k in allowed}

        serializer = self.get_serializer(order, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(self.get_serializer(order).data)

    @staticmethod
    def _calculate_shipping_fee(cart_items) -> Decimal:
        seen_vendors: set[int] = set()
        total_fee = Decimal('0')

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
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = (
            OrderItem.objects
            .select_related('order', 'product_variant', 'vendor')
            .prefetch_related('commission')
        )

        if role == 'admin':
            return qs.all()

        if role == 'vendor':
            try:
                return qs.filter(vendor=user.vendor_profile)
            except VendorProfile.DoesNotExist:
                return qs.none()

        return qs.filter(order__user=user)


class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = Shipment.objects.select_related(
            'order_item__order__user',
            'order_item__vendor',
        )

        if role == 'admin':
            return qs.all()

        if role == 'vendor':
            try:
                return qs.filter(order_item__vendor=user.vendor_profile)
            except VendorProfile.DoesNotExist:
                return qs.none()

        return qs.filter(order_item__order__user=user)

    def perform_create(self, serializer) -> None:
        order_item = serializer.validated_data['order_item']
        user = self.request.user
        role = getattr(user, 'role', None)

        if role == 'vendor':
            try:
                vendor_profile = user.vendor_profile
            except VendorProfile.DoesNotExist:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('Vendor profile not found.')

            if order_item.vendor_id != vendor_profile.id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You can only create shipments for your own order items.')

        serializer.save()


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = Payment.objects.select_related('order__user')

        if role == 'admin':
            return qs.all()

        return qs.filter(order__user=user)

    @action(detail=False, methods=['post'], url_path='create-intent')
    def create_payment_intent(self, request: Request) -> Response:
        order_id = request.data.get('order_id')
        if not order_id:
            return Response({'detail': 'order_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.select_related('user').get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status == Order.PaymentStatus.PAID:
            return Response({'detail': 'Order is already paid.'}, status=status.HTTP_400_BAD_REQUEST)

        existing_payment = getattr(order, 'payment', None)
        if existing_payment and existing_payment.payment_intent_id:
            try:
                intent = stripe.PaymentIntent.retrieve(existing_payment.payment_intent_id)
                return Response({'client_secret': intent.client_secret})
            except stripe.error.StripeError:
                pass

        amount_cents = int(order.total_amount * 100)

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                metadata={
                    'order_id': str(order.id),
                    'user_id': str(request.user.id),
                },
            )
        except stripe.error.StripeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        Payment.objects.update_or_create(
            order=order,
            defaults={
                'gateway': Payment.Gateway.STRIPE,
                'amount': order.total_amount,
                'payment_intent_id': intent.id,
                'status': Payment.Status.PENDING,
            },
        )

        return Response({'client_secret': intent.client_secret})

    @staticmethod
    def _handle_payment_succeeded(intent: dict) -> None:
        intent_id = intent.get('id')
        try:
            payment = Payment.objects.select_related('order').get(payment_intent_id=intent_id)
        except Payment.DoesNotExist:
            return

        with transaction.atomic():
            payment.status = Payment.Status.PAID
            payment.save(update_fields=['status'])

            order = payment.order
            order.payment_status = Order.PaymentStatus.PAID
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=['payment_status', 'status'])

            Commission.objects.filter(
                order_item__order=order,
                status=Commission.Status.PENDING,
            ).update(status=Commission.Status.CLEARED)

    @staticmethod
    def _handle_payment_failed(intent: dict) -> None:
        intent_id = intent.get('id')
        try:
            payment = Payment.objects.select_related('order').get(payment_intent_id=intent_id)
        except Payment.DoesNotExist:
            return

        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])

class StripeWebhookView(View):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)

        if event['type'] == 'payment_intent.succeeded':
            PaymentViewSet._handle_payment_succeeded(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            PaymentViewSet._handle_payment_failed(event['data']['object'])

        return HttpResponse(status=200)

class CommissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = Commission.objects.select_related('vendor', 'order_item')

        if role == 'admin':
            return qs.all()

        try:
            return qs.filter(vendor=user.vendor_profile)
        except VendorProfile.DoesNotExist:
            return qs.none()


class PayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        qs = (
            Payout.objects
            .select_related('vendor')
            .prefetch_related('items__commission')
        )

        if role == 'admin':
            return qs.all()

        try:
            return qs.filter(vendor=user.vendor_profile)
        except VendorProfile.DoesNotExist:
            return qs.none()