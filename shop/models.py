from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils import timezone
import uuid

# --------------------------- User Side  ---------------------------------------------------------

class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    phone = models.CharField(max_length=11, unique=True, null=True, blank=True)
    profile_image = models.ImageField(upload_to='profiles-photos/', null=True, blank=True)
    wishlist_share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"This is {self.user.username}"


class Address(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    full_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=11)
    full_address = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} - {self.full_address}"


# --------------------------- Product Catalog ------------------------------------------------------

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    image = models.ImageField(upload_to='categories-images/', blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='children'
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='brands-logos/', blank=True, null=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Price you paid to acquire/manufacture this product — used to calculate profit"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='products'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_active_flash_sale(self):
        now = timezone.now()
        return self.flash_sales.filter(start_time__lte=now, end_time__gte=now).first()

    @property
    def average_rating(self):
        result = self.reviews.aggregate(avg=models.Avg('rating'))['avg']
        return round(result, 1) if result is not None else None

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def profit_per_unit(self):
        return self.base_price - self.cost_price

    @property
    def profit_margin_percent(self):
        if self.base_price:
            return round((self.profit_per_unit / self.base_price) * 100, 2)
        return 0

    def get_related_products(self, limit=6):
        related = Product.objects.filter(
            category=self.category,
            is_active=True
        ).exclude(id=self.id)

        if related.count() < limit and self.brand:
            brand_related = Product.objects.filter(
                brand=self.brand,
                is_active=True
            ).exclude(id=self.id).exclude(id__in=related.values_list('id', flat=True))
            related = list(related) + list(brand_related)
            return related[:limit]

        return related[:limit]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='products-images/')
    color = models.CharField(
        max_length=30, blank=True,
        help_text="Which color this photo shows (must match a variant's color exactly, e.g. 'Black'). Leave empty for a general/default photo."
    )

    def __str__(self):
        return f"Image of {self.product.name}"


class ProductVariant(models.Model):

    SIZE_CHOICES = (
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Double Extra Large'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    size = models.CharField(max_length=10, blank=True, choices=SIZE_CHOICES)
    color = models.CharField(max_length=30, blank=True)
    sku = models.CharField(max_length=50)
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)

    @property
    def original_price(self):
        return self.product.base_price

    @property
    def price(self):
        flash_sale = self.product.get_active_flash_sale()
        if flash_sale:
            return round(self.product.base_price * (1 - flash_sale.discount_percent / 100), 2)
        if self.price_override is not None:
            return self.price_override
        return self.product.base_price

    @property
    def is_on_sale(self):
        flash_sale = self.product.get_active_flash_sale()
        if flash_sale:
            return True
        return self.price_override is not None and self.price_override < self.product.base_price

    def __str__(self):
        return f"{self.product.name} - {self.size}/{self.color}"


# ---------------------- Cart and Order ------------------------------------------------------------

class Cart(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='cart'
    )
    session_key = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Cart #{self.id}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'variant')

    def __str__(self):
        return f"{self.quantity} x {self.variant}"


class Coupon(models.Model):
    coupon_code = models.CharField(max_length=20, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=0)
    times_used = models.PositiveIntegerField(default=0)

    def is_valid(self):
        if not (self.valid_from <= now() <= self.valid_to):
            return False
        if self.usage_limit > 0 and self.times_used >= self.usage_limit:
            return False
        return True

    def apply_discount(self, amount):
        if self.is_valid():
            discount = amount * (self.discount_percent / 100)
            return round(discount, 2)
        return 0

    def __str__(self):
        return self.coupon_code


class Order(models.Model):
    ORDER_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
        ('refunded', 'Refunded'),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, #guest mode ar jnno
        blank=True, # guest mode ar jnno
        related_name='orders'
    )
    order_number = models.CharField(max_length=30, unique=True)
    public_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    coupon_discount = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    shipping_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True
    )
    guest_name = models.CharField(max_length=100, blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_address = models.CharField(max_length=200, blank=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def apply_coupon(self, coupon_code):
        try:
            coupon = Coupon.objects.get(coupon_code=coupon_code)

            if not coupon.is_valid():
                return {"error": "Invalid or fully used coupon"}

            discount = coupon.apply_discount(self.total_amount)
            self.coupon = coupon
            self.coupon_discount = discount
            self.total_amount -= discount
            self.save()

            coupon.times_used += 1
            coupon.save()

            return {"success": f"Coupon applied successfully! Discount: {discount}"}

        except Coupon.DoesNotExist:
            return {"error": "Coupon not found!"}

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True
    )
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.variant}"


class Payment(models.Model):
    METHOD_CHOICES = (
        ('cod', 'Cash on Delivery'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('card', 'Card'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment of {self.order.order_number}"


class Review(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}, {self.rating}"


class Wishlist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class FlashSale(models.Model):
    title = models.CharField(max_length=100, default='Flash Sale')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    products = models.ManyToManyField(Product, related_name='flash_sales', blank=True)

    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    def __str__(self):
        return f"{self.title} (-{self.discount_percent}%)"


class StockNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_notifications')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='stock_notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'variant')

    def __str__(self):
        return f"{self.user.username} - {self.variant}"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class SizeChart(models.Model):
    UNIT_CHOICES = (
        ('in', 'Inches'),
        ('cm', 'Centimeters'),
    )
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, null=True, blank=True, related_name='size_chart'
    )
    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, null=True, blank=True, related_name='size_chart'
    )
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in')

    def __str__(self):
        if self.product:
            return f"Size Chart - {self.product.name}"
        if self.category:
            return f"Size Chart - {self.category.name} (default)"
        return "Size Chart (unassigned)"


class SizeChartRow(models.Model):
    size_chart = models.ForeignKey(
        SizeChart,
        on_delete=models.CASCADE,
        related_name='rows'
    )
    size = models.CharField(max_length=20)
    chest = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    waist = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    hip = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    length = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        unique_together = ('size_chart', 'size')
        ordering = ['id']

    def __str__(self):
        return f"{self.size_chart} - {self.size}"


class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='return_request'
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Return - {self.order.order_number} ({self.status})"