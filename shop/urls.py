from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, CategoryViewSet, BrandViewSet, TagViewSet, ProductViewSet,
    AddressViewSet, UserProfileViewSet, CartViewSet,
    OrderViewSet, PaymentViewSet, ReviewViewSet, WishlistViewSet, InitiatePaymentView, PaymentSuccessView,
    PaymentFailView, PaymentCancelView, UpdateAccountView, ContactMessageView, ActiveFlashSaleView, StockNotificationViewSet, OrderInvoiceView, PasswordResetConfirmView, PasswordResetRequestView, NewsletterSubscribeView
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('brands', BrandViewSet, basename='brand')
router.register('tags', TagViewSet, basename='tag')
router.register('products', ProductViewSet, basename='product')
router.register('addresses', AddressViewSet, basename='address')
router.register('profile', UserProfileViewSet, basename='profile')
router.register('cart', CartViewSet, basename='cart')
router.register('orders', OrderViewSet, basename='order')
router.register('payments', PaymentViewSet, basename='payment')
router.register('reviews', ReviewViewSet, basename='review')
router.register('wishlist', WishlistViewSet, basename='wishlist')
router.register('stock-notifications', StockNotificationViewSet, basename='stock-notification')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('contact/', ContactMessageView.as_view(), name='contact'),
    path('flash-sale/active/', ActiveFlashSaleView.as_view(), name='active-flash-sale'),
    path('orders/<int:order_id>/invoice/', OrderInvoiceView.as_view(), name='order-invoice'),
    path('update-account/', UpdateAccountView.as_view(), name='update-account'),
    path('payment/initiate/<int:order_id>/', InitiatePaymentView.as_view(), name='payment-initiate'),
    path('payment/success/<int:order_id>/', PaymentSuccessView.as_view(), name='payment-success'),
    path('payment/fail/<int:order_id>/', PaymentFailView.as_view(), name='payment-fail'),
    path('payment/cancel/<int:order_id>/', PaymentCancelView.as_view(), name='payment-cancel'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
]