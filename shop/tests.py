from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import (
    Category, Brand, Product, ProductVariant,
    Cart, CartItem, Address, Order, OrderItem,
    UserProfile, Coupon
)
from django.utils.timezone import now, timedelta


class UserProfileSignalTest(TestCase):
    def test_profile_auto_created_on_user_registration(self):
        user = User.objects.create_user(username='testuser', password='pass1234')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())


class ProductModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='T-Shirts')
        self.brand = Brand.objects.create(name='Urban Threads')
        self.product = Product.objects.create(
            name='Cotton T-Shirt',
            description='Test product',
            base_price=850,
            category=self.category,
            brand=self.brand
        )

    def test_slug_auto_generated(self):
        self.assertEqual(self.product.slug, 'cotton-t-shirt')

    def test_product_str(self):
        self.assertEqual(str(self.product), 'Cotton T-Shirt')


class ProductVariantTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='T-Shirts')
        self.product = Product.objects.create(
            name='Cotton T-Shirt',
            base_price=850,
            category=self.category
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            size='M',
            color='Black',
            sku='TSH-BLK-M',
            stock_quantity=20
        )

    def test_price_uses_base_price_when_no_override(self):
        self.assertEqual(self.variant.price, 850)

    def test_price_uses_override_when_set(self):
        self.variant.price_override = 900
        self.variant.save()
        self.assertEqual(self.variant.price, 900)


class CartTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cartuser', password='pass1234')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='T-Shirts')
        self.product = Product.objects.create(
            name='Cotton T-Shirt', base_price=850, category=self.category
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size='M', color='Black',
            sku='TSH-BLK-M', stock_quantity=20
        )

    def test_add_item_creates_cart_item(self):
        response = self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id,
            'quantity': 2
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().quantity, 2)

    def test_add_same_item_twice_increases_quantity(self):
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 2
        })
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 3
        })
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.first().quantity, 5)

    def test_remove_item(self):
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 2
        })
        cart = Cart.objects.get(user=self.user)
        item = cart.items.first()
        response = self.client.post('/api/shop/cart/remove_item/', {
            'item_id': item.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cart.items.count(), 0)


class OrderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='orderuser', password='pass1234')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='T-Shirts')
        self.product = Product.objects.create(
            name='Cotton T-Shirt', base_price=850, category=self.category
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size='M', color='Black',
            sku='TSH-BLK-M', stock_quantity=20
        )
        self.address = Address.objects.create(
            user=self.user, full_name='Test User', phone='01700000000',
            full_address='Dhaka, Bangladesh'
        )

    def test_order_fails_with_empty_cart(self):
        response = self.client.post('/api/shop/orders/', {
            'shipping_address_id': self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_creation_reduces_stock(self):
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 5
        })
        initial_stock = self.variant.stock_quantity

        response = self.client.post('/api/shop/orders/', {
            'shipping_address_id': self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock - 5)

    def test_order_fails_when_stock_insufficient(self):
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 100
        })
        response = self.client.post('/api/shop/orders/', {
            'shipping_address_id': self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cart_cleared_after_order(self):
        self.client.post('/api/shop/cart/add_item/', {
            'variant_id': self.variant.id, 'quantity': 2
        })
        self.client.post('/api/shop/orders/', {
            'shipping_address_id': self.address.id
        })
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)


class CouponTest(TestCase):
    def setUp(self):
        self.coupon = Coupon.objects.create(
            coupon_code='SAVE10',
            discount_percent=10,
            valid_from=now() - timedelta(days=1),
            valid_to=now() + timedelta(days=10),
            usage_limit=5
        )

    def test_coupon_is_valid_within_date_range(self):
        self.assertTrue(self.coupon.is_valid())

    def test_coupon_discount_calculation(self):
        discount = self.coupon.apply_discount(1000)
        self.assertEqual(discount, 100)

    def test_expired_coupon_is_invalid(self):
        self.coupon.valid_to = now() - timedelta(days=1)
        self.coupon.save()
        self.assertFalse(self.coupon.is_valid())


class ProductFilterTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name='T-Shirts')
        Product.objects.create(name='Cheap Shirt', base_price=300, category=self.category)
        Product.objects.create(name='Expensive Shirt', base_price=2000, category=self.category)

    def test_price_range_filter(self):
        response = self.client.get('/api/shop/products/?min_price=1000&max_price=3000')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Expensive Shirt')

    def test_search_filter(self):
        response = self.client.get('/api/shop/products/?search=Cheap')
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Cheap Shirt')