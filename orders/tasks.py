from __future__ import annotations

import logging

import stripe
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _send_email(subject: str, to: str, text_body: str, html_body: str | None = None) -> None:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    if html_body:
        msg.attach_alternative(html_body, 'text/html')
    msg.send()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation_email(self, order_id: int) -> None:
    from .models import Order

    try:
        order = (
            Order.objects
            .select_related('user', 'shipping_address')
            .prefetch_related('items__product_variant', 'items__vendor')
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        logger.warning('send_order_confirmation_email: Order %s not found.', order_id)
        return

    subject = f'Order #{order.id} Confirmed — Thank you for your purchase!'
    context = {'order': order, 'user': order.user}

    try:
        html_body = render_to_string('emails/order_confirmation.html', context)
        text_body = render_to_string('emails/order_confirmation.txt', context)
        _send_email(subject, order.user.email, text_body, html_body)
    except Exception as exc:
        logger.exception('send_order_confirmation_email failed for order %s.', order_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_vendor_new_order_notification(self, order_id: int, vendor_id: int) -> None:
    from .models import Order, OrderItem
    from accounts.models import VendorProfile

    try:
        vendor = VendorProfile.objects.select_related('user').get(pk=vendor_id)
    except VendorProfile.DoesNotExist:
        logger.warning('send_vendor_new_order_notification: VendorProfile %s not found.', vendor_id)
        return

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('send_vendor_new_order_notification: Order %s not found.', order_id)
        return

    vendor_items = (
        OrderItem.objects
        .select_related('product_variant')
        .filter(order=order, vendor=vendor)
    )

    subject = f'New Order #{order.id} — Action Required'
    context = {'order': order, 'vendor': vendor, 'items': vendor_items}

    try:
        html_body = render_to_string('emails/vendor_new_order.html', context)
        text_body = render_to_string('emails/vendor_new_order.txt', context)
        _send_email(subject, vendor.user.email, text_body, html_body)
    except Exception as exc:
        logger.exception(
            'send_vendor_new_order_notification failed for order %s vendor %s.',
            order_id, vendor_id,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_status_update_email(self, order_id: int) -> None:
    from .models import Order

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('send_order_status_update_email: Order %s not found.', order_id)
        return

    subject = f'Order #{order.id} Status Update — {order.get_status_display()}'
    context = {'order': order, 'user': order.user}

    try:
        html_body = render_to_string('emails/order_status_update.html', context)
        text_body = render_to_string('emails/order_status_update.txt', context)
        _send_email(subject, order.user.email, text_body, html_body)
    except Exception as exc:
        logger.exception('send_order_status_update_email failed for order %s.', order_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_cancelled_email(self, order_id: int) -> None:
    from .models import Order

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('send_order_cancelled_email: Order %s not found.', order_id)
        return

    subject = f'Order #{order.id} Cancelled'
    context = {'order': order, 'user': order.user}

    try:
        html_body = render_to_string('emails/order_cancelled.html', context)
        text_body = render_to_string('emails/order_cancelled.txt', context)
        _send_email(subject, order.user.email, text_body, html_body)
    except Exception as exc:
        logger.exception('send_order_cancelled_email failed for order %s.', order_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def process_stripe_refund(self, order_id: int) -> None:
    from .models import Order, Payment, Commission

    try:
        order = Order.objects.select_related('payment').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('process_stripe_refund: Order %s not found.', order_id)
        return

    payment = getattr(order, 'payment', None)
    if payment is None:
        logger.warning('process_stripe_refund: No payment record for order %s.', order_id)
        return

    if payment.status != Payment.Status.PAID:
        logger.info('process_stripe_refund: Payment for order %s is not in PAID state.', order_id)
        return

    if not payment.payment_intent_id:
        logger.warning('process_stripe_refund: No payment_intent_id for order %s.', order_id)
        return

    try:
        stripe.Refund.create(payment_intent=payment.payment_intent_id)
    except stripe.error.StripeError as exc:
        logger.exception('process_stripe_refund: Stripe error for order %s.', order_id)
        raise self.retry(exc=exc)

    with transaction.atomic():
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=['status'])

        order.payment_status = Order.PaymentStatus.REFUNDED
        order.save(update_fields=['payment_status'])

        Commission.objects.filter(
            order_item__order=order,
        ).update(status=Commission.Status.PENDING)

    logger.info('process_stripe_refund: Refund completed for order %s.', order_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payout_initiated_email(self, payout_id: int) -> None:
    from .models import Payout

    try:
        payout = Payout.objects.select_related('vendor__user').get(pk=payout_id)
    except Payout.DoesNotExist:
        logger.warning('send_payout_initiated_email: Payout %s not found.', payout_id)
        return

    subject = f'Payout of {payout.amount} Initiated'
    context = {'payout': payout, 'vendor': payout.vendor}

    try:
        html_body = render_to_string('emails/payout_initiated.html', context)
        text_body = render_to_string('emails/payout_initiated.txt', context)
        _send_email(subject, payout.vendor.user.email, text_body, html_body)
    except Exception as exc:
        logger.exception('send_payout_initiated_email failed for payout %s.', payout_id)
        raise self.retry(exc=exc)