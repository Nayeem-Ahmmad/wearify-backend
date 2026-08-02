from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings


from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    ProductImage, ProductVariant, Cart, CartItem, Coupon,
    Order, OrderItem, Payment, Review, Wishlist, FlashSale
)
from .tasks import send_order_confirmation_email_task


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['size', 'color', 'sku', 'price_override', 'stock_quantity']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'brand', 'base_price', 'is_active', 'created_at']
    list_filter = ['is_active', 'category', 'brand']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['variant', 'quantity', 'price_at_purchase']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
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
                send_order_confirmation_email_task.delay(order.id)
                approved_count += 1

        self.message_user(request, f'{approved_count} order(s) approved and customer notified.', messages.SUCCESS)

    approve_orders.short_description = "Approve selected orders & notify customer"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'method', 'status', 'transaction_id', 'paid_at']
    list_filter = ['method', 'status']
    search_fields = ['order__order_number', 'transaction_id']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['coupon_code', 'discount_percent', 'valid_from', 'valid_to', 'usage_limit']
    search_fields = ['coupon_code']

@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ['title', 'discount_percent', 'start_time', 'end_time']
    filter_horizontal = ['products']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['product__name', 'user__username']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session_key']


admin.site.register(UserProfile)
admin.site.register(Address)
admin.site.register(CartItem)
admin.site.register(Wishlist)