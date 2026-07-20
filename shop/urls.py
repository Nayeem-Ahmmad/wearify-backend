from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, CategoryViewSet, BrandViewSet, TagViewSet, ProductViewSet,
    AddressViewSet, UserProfileViewSet, CartViewSet,
    OrderViewSet, PaymentViewSet, ReviewViewSet, WishlistViewSet
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

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
]