from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_order_confirmation_email_task(order_id):
    from .models import Order
    try:
        order = Order.objects.get(id=order_id)
        send_mail(
            subject=f'Your Order is Confirmed - {order.order_number}',
            message=(
                f'Hi {order.user.username},\n\n'
                f'Great news! Your order has been confirmed and is now being processed.\n\n'
                f'Order Number : {order.order_number}\n'
                f'Total Amount : {order.total_amount} BDT\n\n'
                f'We will notify you once your order is shipped.\n\n'
                f'Thank you for shopping with Wearify!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
        logger.info(f"Confirmation email sent for order {order.order_number}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for email task")


@shared_task
def notify_admin_new_order_task(order_id):
    from .models import Order
    try:
        order = Order.objects.get(id=order_id)
        items_list = "\n".join(
            f"  - {item.variant.product.name} ({item.variant.size}/{item.variant.color}) x{item.quantity}"
            for item in order.items.all()
        )
        send_mail(
            subject=f'New Order Received - {order.order_number}',
            message=(
                f'A new order has been placed on Wearify.\n\n'
                f'Order Number : {order.order_number}\n'
                f'Customer     : {order.user.username} ({order.user.email})\n'
                f'Total Amount : {order.total_amount} BDT\n'
                f'Shipping To  : {order.shipping_address.full_address if order.shipping_address else "N/A"}\n'
                f'Phone        : {order.shipping_address.phone if order.shipping_address else "N/A"}\n\n'
                f'Items:\n{items_list}\n\n'
                f'Please call the customer to confirm, then approve this order from the admin panel.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )
        logger.info(f"Admin notification sent for order {order.order_number}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for admin email task")


@shared_task
def send_payment_success_email_task(order_id):
    from .models import Order
    try:
        order = Order.objects.get(id=order_id)
        send_mail(
            subject=f'Payment Successful - {order.order_number}',
            message=(
                f'Hi {order.user.username},\n\n'
                f'Your payment for order {order.order_number} has been received successfully.\n'
                f'Amount: {order.total_amount} BDT\n\n'
                f'Thank you for shopping with Wearify!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
        logger.info(f"Payment success email sent for order {order.order_number}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for payment email task")