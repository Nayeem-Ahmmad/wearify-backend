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
def send_order_confirmation_email(sender, instance, created, **kwargs):
    if created:
        send_mail(
            subject=f'Order Confirmation - {instance.order_number}',
            message=(
                f'Hi {instance.user.username},\n\n'
                f'Your order {instance.order_number} has been placed successfully.\n'
                f'Total amount: {instance.total_amount} BDT\n\n'
                f'Thank you for shopping with Wearify!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.user.email],
            fail_silently=False,
        )


@receiver(post_save, sender=Payment)
def send_payment_status_email(sender, instance, created, **kwargs):
    if not created and instance.status in ['paid', 'completed']:
        send_mail(
            subject=f'Payment Successful - {instance.order.order_number}',
            message=(
                f'Hi {instance.order.user.username},\n\n'
                f'Your payment for order {instance.order.order_number} has been received successfully.\n'
                f'Amount: {instance.order.total_amount} BDT\n\n'
                f'Thank you for shopping with Wearify!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.order.user.email],
            fail_silently=False,
        )