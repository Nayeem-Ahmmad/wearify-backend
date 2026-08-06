from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation_email_task(self, order_id): 
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
                    <td style="padding:12px 0;border-bottom:1px solid #f1f5f9;color:#0f172a;font-size:15px;">
                        {item.variant.product.name}<br>
                        <span style="color:#94a3b8;font-size:13px;">
                            {item.variant.size}/{item.variant.color} &times; {item.quantity}
                        </span>
                    </td>
                    <td style="padding:12px 0;border-bottom:1px solid #f1f5f9;color:#0f172a;font-size:15px;text-align:right;vertical-align:top;white-space:nowrap;">
                        {item.price_at_purchase * item.quantity} BDT
                    </td>
                </tr>
            """

        coupon_row = ""
        if order.coupon:
            coupon_row = f"""
                <tr>
                    <td style="padding:0 0 12px;color:#16a34a;font-size:14px;">Coupon used — get {int(order.coupon.discount_percent)}% discount</td>
                    <td style="padding:0 0 12px;color:#16a34a;font-size:14px;text-align:right;white-space:nowrap;">-{order.coupon_discount} BDT</td>
                </tr>
            """

        items_rows += f"""
            <tr>
                <td style="padding:12px 0 4px;color:#64748b;font-size:14px;">Subtotal</td>
                <td style="padding:12px 0 4px;color:#0f172a;font-size:14px;text-align:right;white-space:nowrap;">{order.total_amount + order.coupon_discount - order.shipping_cost} BDT</td>
            </tr>
            <tr>
                <td style="padding:0 0 12px;color:#64748b;font-size:14px;">Shipping</td>
                <td style="padding:0 0 12px;color:#0f172a;font-size:14px;text-align:right;white-space:nowrap;">
                    {'FREE' if order.shipping_cost == 0 else f'{order.shipping_cost} BDT'}
                </td>
            </tr>
            {coupon_row}
            <tr>
                <td style="padding:14px 0;border-top:2px solid #e2e8f0;font-weight:700;color:#0f172a;font-size:17px;">Total</td>
                <td style="padding:14px 0;border-top:2px solid #e2e8f0;font-weight:700;color:#2563EB;font-size:17px;text-align:right;white-space:nowrap;">{order.total_amount} BDT</td>
            </tr>
        """

        shipping_block = ""
        if order.shipping_address:
            shipping_block = (
                f'\nShip To      : {order.shipping_address.full_name}\n'
                f'Address      : {order.shipping_address.full_address}\n'
                f'Phone        : {order.shipping_address.phone}\n'
            )

        text_content = (
            f'Hi {order.user.username},\n\n'
            f'Great news! Your order has been confirmed and is now being processed.\n\n'
            f'Order Number : {order.order_number}\n'
            f'Order Date   : {order.created_at.strftime("%B %d, %Y")}\n'
            f'Total Amount : {order.total_amount} BDT\n'
            f'{shipping_block}\n'
            f'Track your order: {tracking_link}\n\n'
            f'We will notify you once your order is shipped.\n\n'
            f'Thank you so much for shopping with Wearify — we truly appreciate your trust in us!\n\n'
            f'Warm regards,\nTeam Wearify'
        )

        shipping_html = ""
        if order.shipping_address:
            shipping_html = f"""
                <div>
                    <p style="margin:0 0 4px;color:#94a3b8;font-size:11px;font-weight:700;letter-spacing:0.05em;">SHIP TO</p>
                    <p style="margin:0;color:#0f172a;font-size:13px;font-weight:600;">{order.shipping_address.full_name}</p>
                    <p style="margin:2px 0 0;color:#64748b;font-size:12px;line-height:1.5;">{order.shipping_address.full_address}</p>
                    <p style="margin:2px 0 0;color:#64748b;font-size:12px;">{order.shipping_address.phone}</p>
                </div>
            """

        html_content = f"""
        <div style="background:#f4f6fb;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
            <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

                <div style="background:linear-gradient(90deg,#2563EB,#9333EA);padding:24px;text-align:center;">
                    <span style="font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.8px;text-shadow:0 1px 3px rgba(0,0,0,0.15);">Wearify</span>
                </div>

                <div style="padding:32px 28px;">
                    <p style="margin:0 0 4px;color:#16a34a;font-size:13px;font-weight:700;letter-spacing:0.05em;">ORDER CONFIRMED</p>
                    <h2 style="margin:0 0 20px;color:#0f172a;font-size:22px;font-weight:700;">Hi {order.user.username}, thanks for your order!</h2>
                    <p style="margin:0 0 24px;color:#475569;font-size:15px;font-weight:500;line-height:1.6;">
                        Great news! Your order has been confirmed and is now being processed. We'll notify you again once it ships.
                    </p>

                    <div style="border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;margin-bottom:24px;">
                        <p style="margin:0 0 14px;color:#0f172a;font-size:15px;font-weight:700;">INVOICE</p>
                        <table style="width:100%;border-collapse:collapse;">
                            <tr>
                                <td style="vertical-align:top;width:50%;">
                                    <p style="margin:0 0 4px;color:#94a3b8;font-size:11px;font-weight:700;letter-spacing:0.05em;">ORDER NUMBER</p>
                                    <p style="margin:0 0 12px;color:#0f172a;font-size:14px;font-weight:700;">{order.order_number}</p>
                                    <p style="margin:0 0 4px;color:#94a3b8;font-size:11px;font-weight:700;letter-spacing:0.05em;">ORDER DATE</p>
                                    <p style="margin:0;color:#0f172a;font-size:13px;">{order.created_at.strftime("%B %d, %Y")}</p>
                                </td>
                                <td style="vertical-align:top;width:50%;">
                                    {shipping_html}
                                </td>
                            </tr>
                        </table>
                    </div>

                    <table style="width:100%;border-collapse:collapse;">
                        {items_rows}
                    </table>

                    <div style="text-align:center;margin:32px 0 8px;">
                        <a href="{tracking_link}"
                           style="background:linear-gradient(90deg,#2563EB,#9333EA);color:#ffffff;padding:14px 36px;border-radius:999px;text-decoration:none;font-weight:600;font-size:15px;display:inline-block;">
                            Track Your Order
                        </a>
                    </div>

                    <div style="border-top:1px solid #f1f5f9;margin-top:28px;padding-top:20px;text-align:center;">
                        <p style="margin:0;color:#0f172a;font-size:14px;font-weight:600;">Thank you so much for shopping with Wearify!</p>
                        <p style="margin:6px 0 0;color:#94a3b8;font-size:12px;">We truly appreciate your trust in us and can't wait for you to receive your order. 💙</p>
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
    except Exception as exc:
        logger.error(f"Failed to send confirmation email (attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}")
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admin_new_order_task(self, order_id):
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
    except Exception as exc:
        logger.error(f"Failed to send admin notification (attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payment_success_email_task(self, order_id):
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
    except Exception as exc:
        logger.error(f"Failed to send payment success email (attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}")
        raise self.retry(exc=exc)




@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_contact_message_task(self, name, email, message):
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
    except Exception as exc:
        logger.error(f"Failed to send contact message email (attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}")
        raise self.retry(exc=exc)



@shared_task
def send_stock_available_email_task(variant_id):
    from .models import ProductVariant, StockNotification

    try:
        variant = ProductVariant.objects.get(id=variant_id)
    except ProductVariant.DoesNotExist:
        logger.error(f"Variant {variant_id} not found for stock notification task")
        return

    notifications = StockNotification.objects.filter(variant=variant).select_related('user')
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    product_link = f"{frontend_url}/product/{variant.product.slug}"

    for notification in notifications:
        user = notification.user
        if not user.email:
            continue
        send_mail(
            subject=f'{variant.product.name} is back in stock!',
            message=(
                f'Hi {user.username},\n\n'
                f'Good news! {variant.product.name} ({variant.size}/{variant.color}) is back in stock.\n\n'
                f'Grab it before it runs out again: {product_link}\n\n'
                f'Thank you for shopping with Wearify!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    notifications.delete()
    logger.info(f"Stock available emails sent for variant {variant_id}")


@shared_task
def send_review_reminder_email_task(order_id):
    from .models import Order

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for review reminder task")
        return

    if order.status != 'delivered':
        return

    items = order.items.all()
    if not items:
        return

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    product_lines = "\n".join(
        f"  - {item.variant.product.name}: {frontend_url}/products/{item.variant.product.slug}#review"
        for item in items
    )

    send_mail(
        subject=f'How was your order {order.order_number}?',
        message=(
            f'Hi {order.user.username},\n\n'
            f'We hope you are enjoying your recent purchase. Please take a moment to review the items below:\n\n'
            f'{product_lines}\n\n'
            f'Thank you for shopping with Wearify!'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        fail_silently=True,
    )
    logger.info(f"Review reminder email sent for order {order.order_number}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email_task(self, user_id, uid, token):
    from django.contrib.auth.models import User
    from django.core.mail import EmailMultiAlternatives

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset email task")
        return

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    reset_link = f'{frontend_url}/reset-password?uid={uid}&token={token}'

    text_content = (
        f'Hi {user.username},\n\n'
        f'We received a request to reset your Wearify password.\n\n'
        f'Reset your password: {reset_link}\n\n'
        f'This link can only be used once. If you did not request this, you can safely ignore this email.\n\n'
        f'Thank you,\nWearify'
    )

    html_content = f"""
    <div style="background:#f4f6fb;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
        <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
            <div style="background:linear-gradient(90deg,#2563EB,#9333EA);padding:24px;text-align:center;">
                <span style="font-size:28px;font-weight:800;color:#ffffff;">Wearify</span>
            </div>
            <div style="padding:32px 28px;">
                <h2 style="margin:0 0 16px;color:#0f172a;font-size:19px;">Reset your password</h2>
                <p style="margin:0 0 24px;color:#475569;font-size:14px;line-height:1.6;">
                    Hi {user.username}, we received a request to reset your Wearify password. Click the button below to choose a new one.
                </p>
                <div style="text-align:center;margin:28px 0;">
                    <a href="{reset_link}"
                       style="background:linear-gradient(90deg,#2563EB,#9333EA);color:#ffffff;padding:14px 36px;border-radius:999px;text-decoration:none;font-weight:600;font-size:14px;display:inline-block;">
                        Reset Password
                    </a>
                </div>
                <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;">
                    This link can only be used once. If you didn't request this, you can safely ignore this email.
                </p>
            </div>
            <div style="background:#0f172a;padding:20px 28px;text-align:center;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">Wearify &middot; wearify.sells@gmail.com</p>
            </div>
        </div>
    </div>
    """

    try:
        email = EmailMultiAlternatives(
            subject='Reset your Wearify password',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        logger.info(f"Password reset email sent to {user.email}")
    except Exception as exc:
        logger.error(f"Failed to send password reset email to {user.email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_flash_sale_email_task(self, flash_sale_id):
    from .models import FlashSale, NewsletterSubscriber
    from django.core.mail import EmailMultiAlternatives

    try:
        flash_sale = FlashSale.objects.get(id=flash_sale_id)
    except FlashSale.DoesNotExist:
        logger.error(f"FlashSale {flash_sale_id} not found for newsletter email task")
        return

    subscribers = NewsletterSubscriber.objects.filter(is_active=True)
    if not subscribers.exists():
        logger.info("No active newsletter subscribers to notify")
        return

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    deals_link = f'{frontend_url}/deals'
    products = list(flash_sale.products.all()[:4])

    products_html = "".join(
        f"""
        <div style="padding:10px 0;border-bottom:1px solid #f1f5f9;">
            <p style="margin:0;color:#0f172a;font-size:14px;font-weight:600;">{p.name}</p>
            <p style="margin:2px 0 0;color:#2563EB;font-size:13px;">
                -{flash_sale.discount_percent}% off — now ৳{round(p.base_price * (1 - flash_sale.discount_percent / 100), 2)}
            </p>
        </div>
        """
        for p in products
    )

    html_content = f"""
    <div style="background:#f4f6fb;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
        <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
            <div style="background:linear-gradient(90deg,#2563EB,#9333EA);padding:24px;text-align:center;">
                <span style="font-size:28px;font-weight:800;color:#ffffff;">Wearify</span>
            </div>
            <div style="padding:32px 28px;">
                <p style="margin:0 0 4px;color:#dc2626;font-size:13px;font-weight:700;letter-spacing:0.05em;">⚡ FLASH SALE LIVE NOW</p>
                <h2 style="margin:0 0 16px;color:#0f172a;font-size:20px;">{flash_sale.title} — {flash_sale.discount_percent}% Off</h2>
                <p style="margin:0 0 20px;color:#475569;font-size:14px;line-height:1.6;">
                    Limited time only! Grab your favorites before this deal ends.
                </p>
                {products_html}
                <div style="text-align:center;margin:28px 0 8px;">
                    <a href="{deals_link}"
                       style="background:linear-gradient(90deg,#2563EB,#9333EA);color:#ffffff;padding:14px 36px;border-radius:999px;text-decoration:none;font-weight:600;font-size:14px;display:inline-block;">
                        Shop the Sale
                    </a>
                </div>
            </div>
            <div style="background:#0f172a;padding:20px 28px;text-align:center;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">Wearify &middot; wearify.sells@gmail.com</p>
            </div>
        </div>
    </div>
    """

    text_content = (
        f'Flash Sale Live Now: {flash_sale.title} — {flash_sale.discount_percent}% off!\n\n'
        f'Shop now: {deals_link}\n\n'
        f'Thank you for shopping with Wearify!'
    )

    try:
        for subscriber in subscribers:
            email = EmailMultiAlternatives(
                subject=f'⚡ {flash_sale.discount_percent}% Off — {flash_sale.title} is Live!',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[subscriber.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=True)
        logger.info(f"Flash sale email sent to {subscribers.count()} subscribers for {flash_sale.title}")
    except Exception as exc:
        logger.error(f"Failed to send flash sale emails: {exc}")
        raise self.retry(exc=exc)