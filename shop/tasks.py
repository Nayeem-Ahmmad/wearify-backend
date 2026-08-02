from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_order_confirmation_email_task(order_id):
    from .models import Order
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    try:
        order = Order.objects.get(id=order_id)
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        tracking_link = f'{frontend_url}/order-confirmation?order_id={order.id}'

        items_rows = ""
        for item in order.items.all():
            items_rows += f"""
                <tr>
                    <td style="padding:12px 0;border-bottom:1px solid #f1f5f9;color:#0f172a;font-size:14px;">
                        {item.variant.product.name}<br>
                        <span style="color:#94a3b8;font-size:12px;">
                            {item.variant.size}/{item.variant.color} &times; {item.quantity}
                        </span>
                    </td>
                    <td style="padding:12px 0;border-bottom:1px solid #f1f5f9;color:#0f172a;font-size:14px;text-align:right;vertical-align:top;white-space:nowrap;">
                        {item.price_at_purchase * item.quantity} BDT
                    </td>
                </tr>
            """

        text_content = (
            f'Hi {order.user.username},\n\n'
            f'Great news! Your order has been confirmed and is now being processed.\n\n'
            f'Order Number : {order.order_number}\n'
            f'Total Amount : {order.total_amount} BDT\n\n'
            f'Track your order: {tracking_link}\n\n'
            f'We will notify you once your order is shipped.\n\n'
            f'Thank you for shopping with Wearify!'
        )

        html_content = f"""
        <div style="background:#f4f6fb;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
            <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

                <div style="background:linear-gradient(90deg,#2563EB,#9333EA);padding:24px;text-align:center;">
                    <span style="font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.8px;font-family:Arial,Helvetica,sans-serif;text-shadow:0 1px 3px rgba(0,0,0,0.15);">Wearify</span>
                </div>

                <div style="padding:32px 28px;">
                    <p style="margin:0 0 4px;color:#16a34a;font-size:13px;font-weight:700;letter-spacing:0.05em;">ORDER CONFIRMED</p>
                    <h2 style="margin:0 0 20px;color:#0f172a;font-size:20px;">Hi {order.user.username}, thanks for your order!</h2>
                    <p style="margin:0 0 24px;color:#475569;font-size:14px;line-height:1.6;">
                        Great news! Your order has been confirmed and is now being processed. We'll notify you again once it ships.
                    </p>

                    <div style="background:#f8fafc;border-radius:12px;padding:16px 20px;margin-bottom:24px;">
                        <p style="margin:0;color:#64748b;font-size:12px;">ORDER NUMBER</p>
                        <p style="margin:4px 0 0;color:#0f172a;font-size:16px;font-weight:700;">{order.order_number}</p>
                    </div>

                    <table style="width:100%;border-collapse:collapse;">
                        {items_rows}
                        <tr>
                            <td style="padding:12px 0 4px;color:#64748b;font-size:13px;">Subtotal</td>
                            <td style="padding:12px 0 4px;color:#0f172a;font-size:13px;text-align:right;white-space:nowrap;">{order.total_amount - order.shipping_cost} BDT</td>
                        </tr>
                        <tr>
                            <td style="padding:0 0 12px;color:#64748b;font-size:13px;">Shipping</td>
                            <td style="padding:0 0 12px;color:#0f172a;font-size:13px;text-align:right;white-space:nowrap;">
                                {'FREE' if order.shipping_cost == 0 else f'{order.shipping_cost} BDT'}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:14px 0;border-top:2px solid #e2e8f0;font-weight:700;color:#0f172a;font-size:15px;">Total</td>
                            <td style="padding:14px 0;border-top:2px solid #e2e8f0;font-weight:700;color:#2563EB;font-size:15px;text-align:right;white-space:nowrap;">{order.total_amount} BDT</td>
                        </tr>
                    </table>

                    <div style="text-align:center;margin:32px 0 8px;">
                        <a href="{tracking_link}"
                           style="background:linear-gradient(90deg,#2563EB,#9333EA);color:#ffffff;padding:14px 36px;border-radius:999px;text-decoration:none;font-weight:600;font-size:14px;display:inline-block;">
                            Track Your Order
                        </a>
                    </div>
                </div>

                <div style="background:#0f172a;padding:24px 28px;text-align:center;">
                    <p style="margin:0 0 6px;color:#ffffff;font-size:14px;font-weight:700;">Wearify</p>
                    <p style="margin:0;color:#94a3b8;font-size:12px;">Gulshan, Dhaka, Bangladesh &middot; wearify.sells@gmail.com</p>
                </div>

            </div>
        </div>
        """

        email = EmailMultiAlternatives(
            subject=f'Your Order is Confirmed - {order.order_number}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

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




@shared_task
def send_contact_message_task(name, email, message):
    try:
        send_mail(
            subject=f'New Contact Message from {name}',
            message=(
                f'Name: {name}\n'
                f'Email: {email}\n\n'
                f'Message:\n{message}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=False,
        )
        logger.info(f"Contact message email sent successfully from {email}")
    except Exception as e:
        logger.error(f"Failed to send contact message email from {email}: {e}")