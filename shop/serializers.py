from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    ProductImage, ProductVariant, Cart, CartItem, Coupon,
    Order, OrderItem, Payment, Review, Wishlist, FlashSale, StockNotification, NewsletterSubscriber, SizeChart, SizeChartRow, ReturnRequest
)

from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="An account with this email already exists.")]
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class ContactMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    message = serializers.CharField()

    # def create(self, validated_data):
    #     user = User.objects.create_user(
    #         username=validated_data['username'],
    #         email=validated_data.get('email', ''),
    #         password=validated_data['password']
    #     )
    #     return user

class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class UserAccountUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email']


class UserProfileSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'phone', 'profile_image', 'wishlist_share_token']
        read_only_fields = ['user', 'wishlist_share_token']


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'user', 'full_name', 'phone', 'full_address', 'is_default']
        read_only_fields = ['user']


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'children', 'image', 'product_count', 'meta_title', 'meta_description']

    def get_children(self, obj):
        return CategorySerializer(obj.children.all(), many=True).data

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name', 'logo']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image', 'color']


class ProductVariantSerializer(serializers.ModelSerializer):
    price = serializers.ReadOnlyField()
    original_price = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_brand = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'product_name', 'product_slug', 'product_brand',
            'product_image', 'size', 'color', 'sku', 'price_override',
            'original_price', 'is_on_sale', 'stock_quantity', 'price'
        ]

    def get_product_brand(self, obj):
        return obj.product.brand.name if obj.product.brand else None

    def get_product_image(self, obj):
        first_image = obj.product.images.filter(color=obj.color).first()
        if not first_image:
            first_image = obj.product.images.first()
        if not first_image:
            return None
        request = self.context.get('request')
        url = first_image.image.url
        return request.build_absolute_uri(url) if request else url


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), source='brand', write_only=True, required=False
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), source='tags', many=True, write_only=True, required=False
    )
    flash_sale_end = serializers.SerializerMethodField()
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    size_chart = serializers.SerializerMethodField()


    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'base_price',
            'flash_sale_end','average_rating', 'review_count',
            'category', 'category_id', 'brand', 'brand_id',
            'tags', 'tag_ids', 'images', 'variants', 'size_chart',
            'is_active', 'created_at', 'meta_title', 'meta_description'
        ]

    def get_flash_sale_end(self, obj):
        flash_sale = obj.get_active_flash_sale()
        return flash_sale.end_time if flash_sale else None
    def get_size_chart(self, obj):
        size_chart = getattr(obj, 'size_chart', None)
        if not size_chart and obj.category:
            size_chart = getattr(obj.category, 'size_chart', None)
        if not size_chart or not size_chart.rows.exists():
            return None
        return SizeChartSerializer(size_chart).data


class CartItemSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), source='variant', write_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'variant', 'variant_id', 'quantity', 'subtotal']
        read_only_fields = ['cart']

    def get_subtotal(self, obj):
        return obj.variant.price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'session_key', 'items', 'total']
        read_only_fields = ['user']

    def get_total(self, obj):
        return sum(item.variant.price * item.quantity for item in obj.items.all())


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'coupon_code', 'discount_percent', 'valid_from', 'valid_to', 'usage_limit', 'times_used']
        read_only_fields = ['times_used']


class OrderItemSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'variant', 'quantity', 'price_at_purchase']
        read_only_fields = ['order']


class OrderCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'coupon_code', 'discount_percent']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'method', 'status', 'transaction_id', 'paid_at']
        read_only_fields = ['order']

class OrderReturnRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = ['id', 'status', 'reason', 'admin_note', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all(), source='shipping_address', write_only=True
    )
    coupon = OrderCouponSerializer(read_only=True)
    return_request = OrderReturnRequestSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'order_number', 'public_token', 'coupon', 'coupon_discount', 'status',
            'shipping_address', 'shipping_address_id', 'shipping_cost',
            'total_amount', 'created_at', 'items', 'payment', 'return_request', 'guest_name', 'guest_phone', 'guest_email', 'guest_address'
        ]
        read_only_fields = ['user', 'order_number', 'total_amount', 'shipping_cost', 'coupon_discount']


class ReviewSerializer(serializers.ModelSerializer):

    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Review
        fields = ['id', 'product', 'user', 'user_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['user']

    def validate(self, data):
        request = self.context.get('request')
        product = data.get('product')
        if request and product:
            if Review.objects.filter(product=product, user=request.user).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError("You have already reviewed this product.")
        return data


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'product', 'product_id']
        read_only_fields = ['user']

class FlashSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlashSale
        fields = ['id', 'title', 'discount_percent', 'start_time', 'end_time', 'products']

class FlashSaleDetailSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = FlashSale
        fields = ['id', 'title', 'discount_percent', 'start_time', 'end_time', 'products']


class StockNotificationSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), source='variant', write_only=True
    )

    class Meta:
        model = StockNotification
        fields = ['id', 'user', 'variant', 'variant_id', 'created_at']
        read_only_fields = ['user', 'created_at']


#--------------Forget password fix-------------------------------------

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'subscribed_at']
        read_only_fields = ['id', 'subscribed_at']


class SizeChartRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SizeChartRow
        fields = ['size', 'chest', 'waist', 'hip', 'length']


class SizeChartSerializer(serializers.ModelSerializer):
    rows = SizeChartRowSerializer(many=True, read_only=True)

    class Meta:
        model = SizeChart
        fields = ['id', 'unit', 'rows']


class ReturnRequestSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = ReturnRequest
        fields = ['id', 'order', 'order_number', 'reason', 'status', 'admin_note', 'created_at']
        read_only_fields = ['status', 'admin_note', 'created_at']


class SharedWishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    class Meta:
        model = Wishlist
        fields = ['id', 'product']