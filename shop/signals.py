from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import UserProfile, OrderItem, Order, Payment


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=OrderItem)
def reduce_stock(sender, instance, created, **kwargs):
    if created:
        variant = instance.variant
        if variant:
            variant.stock_quantity = max(0, variant.stock_quantity - instance.quantity)
            variant.save()


@receiver(post_save, sender=Order)
def notify_admin_new_order(sender, instance, created, **kwargs):
    if created:
        items_list = "\n".join(
            f"  - {item.variant.product.name} ({item.variant.size}/{item.variant.color}) x{item.quantity}"
            for item in instance.items.all()
        )
        send_mail(
            subject=f'🛒 New Order Received - {instance.order_number}',
            message=(
                f'A new order has been placed on Wearify.\n\n'
                f'Order Number : {instance.order_number}\n'
                f'Customer     : {instance.user.username} ({instance.user.email})\n'
                f'Total Amount : {instance.total_amount} BDT\n'
                f'Shipping To  : {instance.shipping_address.full_address if instance.shipping_address else "N/A"}\n'
                f'Phone        : {instance.shipping_address.phone if instance.shipping_address else "N/A"}\n\n'
                f'Items:\n{items_list}\n\n'
                f'Please call the customer to confirm, then approve this order from the admin panel.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )

