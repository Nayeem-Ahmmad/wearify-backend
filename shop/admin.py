


from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings

from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline

import csv
import io
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    ProductImage, ProductVariant, Cart, CartItem, Coupon,
    Order, OrderItem, Payment, Review, Wishlist, FlashSale, NewsletterSubscriber, SizeChartRow, SizeChart, ReturnRequest, Banner
)
from .tasks import send_order_confirmation_email_task
from .tasks import send_flash_sale_email_task

#------------------- Maintenance mode -------------------------------
from .models import SiteSettings
# @admin.register(SiteSettings)
# class SiteSettingsAdmin(ModelAdmin):
#     list_display = ['maintenance_mode']

#     def has_add_permission(self, request):
#         return not SiteSettings.objects.exists()

#     def has_delete_permission(self, request, obj=None):
#         return False

@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    list_display = ['maintenance_mode']

    fieldsets = (
        ('Maintenance Mode', {
            'fields': ('maintenance_mode', 'maintenance_message'),
            'description': 'Turn this ON to temporarily take the website offline for visitors. Admin panel will still be accessible.',
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.objects.first()
        if obj:
            return redirect('admin:shop_sitesettings_change', obj.id)
        return redirect('admin:shop_sitesettings_add')  

@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ['title', 'image_preview', 'is_active', 'order', 'created_at']
    list_editable = ['is_active', 'order']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:50px; border-radius:6px;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Preview'

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'color', 'image_preview']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 8px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Preview'


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['size', 'color', 'sku', 'price_override', 'stock_quantity']


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ['name', 'category', 'brand', 'base_price', 'cost_price', 'profit_display', 'is_active', 'first_image_preview', 'created_at']
    list_filter = ['is_active', 'category', 'brand']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]
    change_list_template = 'admin/shop/product/change_list.html'

    # class Media:
    #         js = ('shop/js/variant_color_sync.js',)

    def profit_display(self, obj):
        return f"৳{obj.profit_per_unit:,.2f} ({obj.profit_margin_percent}%)"
    profit_display.short_description = "Profit / Margin"

    def first_image_preview(self, obj):
        first_image = obj.images.first()
        if first_image and first_image.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 8px;" />',
                first_image.image.url
            )
        return "No Image"
    first_image_preview.short_description = 'Image'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='shop_product_import_csv'),
            path('export-csv/', self.admin_site.admin_view(self.export_csv), name='shop_product_export_csv'),
        ]
        return custom_urls + urls

    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'product_name', 'description', 'base_price', 'cost_price', 'category', 'brand', 'tags',
            'is_active', 'color', 'size', 'sku', 'price_override', 'stock_quantity'
        ])
        for variant in ProductVariant.objects.select_related('product', 'product__category', 'product__brand').all():
            p = variant.product
            writer.writerow([
                p.name, p.description, p.base_price, p.cost_price,
                p.category.slug if p.category else '',
                p.brand.name if p.brand else '',
                ','.join(p.tags.values_list('name', flat=True)),
                p.is_active,
                variant.color, variant.size, variant.sku,
                variant.price_override or '', variant.stock_quantity,
            ])
        return response

    def import_csv(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file or not csv_file.name.endswith('.csv'):
                self.message_user(request, 'Please upload a valid .csv file', messages.ERROR)
                return redirect('..')

            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))

            created_products, created_variants, errors = 0, 0, []

            for i, row in enumerate(reader, start=2):
                try:
                    name = row['product_name'].strip()
                    if not name:
                        continue

                    category = None
                    if row.get('category'):
                        category = Category.objects.filter(slug=row['category'].strip()).first()

                    brand = None
                    if row.get('brand'):
                        brand, _ = Brand.objects.get_or_create(name=row['brand'].strip())

                    product, product_created = Product.objects.get_or_create(
                        name=name,
                        defaults={
                            'description': row.get('description', ''),
                            'base_price': row['base_price'],
                            'cost_price': row.get('cost_price') or 0,
                            'category': category,
                            'brand': brand,
                            'is_active': row.get('is_active', 'True').strip().lower() in ('true', '1', 'yes'),
                        }
                    )
                    if product_created:
                        created_products += 1
                        if row.get('tags'):
                            tag_names = [t.strip() for t in row['tags'].split(',') if t.strip()]
                            for tag_name in tag_names:
                                tag, _ = Tag.objects.get_or_create(name=tag_name)
                                product.tags.add(tag)

                    sku = row.get('sku', '').strip()
                    if sku and not ProductVariant.objects.filter(sku=sku).exists():
                        ProductVariant.objects.create(
                            product=product,
                            color=row.get('color', '').strip(),
                            size=row.get('size', '').strip(),
                            sku=sku,
                            price_override=row.get('price_override') or None,
                            stock_quantity=row.get('stock_quantity') or 0,
                        )
                        created_variants += 1

                except Exception as e:
                    errors.append(f"Row {i}: {str(e)}")

            msg = f'{created_products} new product(s), {created_variants} new variant(s) imported.'
            if errors:
                msg += f' {len(errors)} row(s) failed: ' + '; '.join(errors[:5])
                self.message_user(request, msg, messages.WARNING)
            else:
                self.message_user(request, msg, messages.SUCCESS)

            return redirect('..')
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Import Products from CSV',
        }
        return render(request, 'admin/shop/product/import_csv.html', context)


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
    list_display = ['coupon_code', 'discount_percent', 'valid_from', 'valid_to', 'usage_limit', 'times_used']
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
    actions = ['notify_subscribers']

    def notify_subscribers(self, request, queryset):
        count = 0
        for flash_sale in queryset:
            send_flash_sale_email_task.delay(flash_sale.id)
            count += 1
        self.message_user(request, f'Notification email queued for {count} flash sale(s).', messages.SUCCESS)

    notify_subscribers.short_description = "Notify newsletter subscribers"


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


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(ModelAdmin):
    list_display = ['email', 'is_active', 'subscribed_at']
    list_filter = ['is_active']
    search_fields = ['email']


class SizeChartRowInline(TabularInline):
    model = SizeChartRow
    extra = 1


@admin.register(SizeChart)
class SizeChartAdmin(ModelAdmin):
    list_display = ['__str__', 'unit']
    list_filter = ['unit']
    inlines = [SizeChartRowInline]


@admin.register(ReturnRequest)
class ReturnRequestAdmin(ModelAdmin):
    list_display = ['order', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['order__order_number']
    readonly_fields = ['order', 'reason', 'created_at']
    actions = ['approve_returns', 'reject_returns']

    def approve_returns(self, request, queryset):
        count = 0
        for rr in queryset.filter(status='pending'):
            rr.status = 'approved'
            rr.resolved_at = timezone.now()
            rr.save()
            rr.order.status = 'returned'
            rr.order.save()
            count += 1
        self.message_user(request, f'{count} return(s) approved.', messages.SUCCESS)
    approve_returns.short_description = "Approve selected returns"

    def reject_returns(self, request, queryset):
        count = queryset.filter(status='pending').update(status='rejected', resolved_at=timezone.now())
        self.message_user(request, f'{count} return(s) rejected.', messages.SUCCESS)
    reject_returns.short_description = "Reject selected returns"