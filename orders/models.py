from django.db import models


class TimeStampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Cart(TimeStampMixin):
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='cart'
    )

    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(TimeStampMixin):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product_variant')

    def __str__(self):
        return f"{self.quantity} x {self.product_variant.variant_name}"


class Order(TimeStampMixin):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='orders'
    )
    shipping_address = models.ForeignKey(
        'accounts.Address', on_delete=models.SET_NULL, null=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Order #{self.id} for {self.user.username}"


class OrderItem(TimeStampMixin):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE
    )
    vendor = models.ForeignKey(
        'accounts.VendorProfile', on_delete=models.CASCADE, related_name='order_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    def __str__(self):
        return f"{self.quantity} x {self.product_variant.variant_name} (Order #{self.order.id})"


class Shipment(TimeStampMixin):
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.CASCADE, related_name='shipment'
    )
    tracking_number = models.CharField(max_length=255, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shipment for OrderItem #{self.order_item.id}"


class Payment(TimeStampMixin):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    class Gateway(models.TextChoices):
        STRIPE = 'stripe', 'Stripe'
        PAYPAL = 'paypal', 'PayPal'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_intent_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    def __str__(self):
        return f"Payment for Order #{self.order.id} — {self.status}"


class Commission(TimeStampMixin):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CLEARED = 'cleared', 'Cleared'
        PAID = 'paid', 'Paid'

    vendor = models.ForeignKey(
        'accounts.VendorProfile', on_delete=models.CASCADE, related_name='commissions'
    )
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.CASCADE, related_name='commission'
    )
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    def __str__(self):
        return f"Commission for {self.vendor.company_name} — {self.commission_amount}"


class Payout(TimeStampMixin):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    vendor = models.ForeignKey(
        'accounts.VendorProfile', on_delete=models.CASCADE, related_name='payouts'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_method = models.CharField(max_length=50)
    payout_intent_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout for {self.vendor.company_name} — {self.status}"


class PayoutItem(TimeStampMixin):
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE, related_name='items')
    commission = models.OneToOneField(
        Commission, on_delete=models.CASCADE, related_name='payout_item'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"PayoutItem #{self.id} — {self.amount}"