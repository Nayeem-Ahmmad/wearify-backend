


from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings

from unfold.admin import ModelAdmin, TabularInline

from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    ProductImage, ProductVariant, Cart, CartItem, Coupon,
    Order, OrderItem, Payment, Review, Wishlist, FlashSale
)
from .tasks import send_order_confirmation_email_task


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'color']


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['size', 'color', 'sku', 'price_override', 'stock_quantity']


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ['name', 'category', 'brand', 'base_price', 'cost_price', 'profit_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'category', 'brand']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]

    class Media:
            js = ('shop/js/variant_color_sync.js',)

    def profit_display(self, obj):
        return f"৳{obj.profit_per_unit:,.2f} ({obj.profit_margin_percent}%)"
    profit_display.short_description = "Profit / Margin"


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'parent']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['variant_photo', 'variant', 'quantity', 'price_at_purchase']

    def variant_photo(self, obj):
        if not obj.variant:
            return "—"
        from django.utils.html import format_html
        image = obj.variant.product.images.filter(color=obj.variant.color).first()
        if not image:
            image = obj.variant.product.images.first()
        if not image:
            return "No photo"
        return format_html('<img src="{}" style="height:60px;border-radius:6px;" />', image.image.url)
    variant_photo.short_description = "Photo"


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ['order_number', 'user', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_number', 'user__username']
    inlines = [OrderItemInline]
    actions = ['approve_orders']

    def approve_orders(self, request, queryset):
        approved_count = 0
        for order in queryset:
            if order.status == 'pending':
                order.status = 'confirmed'
                order.save()
                approved_count += 1

        self.message_user(request, f'{approved_count} order(s) approved and customer notified.', messages.SUCCESS)

    approve_orders.short_description = "Approve selected orders & notify customer"


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ['order', 'method', 'status', 'transaction_id', 'paid_at']
    list_filter = ['method', 'status']
    search_fields = ['order__order_number', 'transaction_id']


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ['coupon_code', 'discount_percent', 'valid_from', 'valid_to', 'usage_limit']
    search_fields = ['coupon_code']


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['product__name', 'user__username']


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ['id', 'user', 'session_key']


@admin.register(FlashSale)
class FlashSaleAdmin(ModelAdmin):
    list_display = ['title', 'discount_percent', 'start_time', 'end_time']
    filter_horizontal = ['products']


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ['user', 'phone']
    search_fields = ['user__username']


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ['full_name', 'user', 'phone', 'is_default']
    search_fields = ['full_name', 'user__username']


@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    list_display = ['cart', 'variant', 'quantity']


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ['user', 'product']
    search_fields = ['user__username', 'product__name']