from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Order, ProductVariant, OrderItem


def dashboard_callback(request, context):
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    orders_qs = Order.objects.exclude(status='cancelled')

    total_sales = sum(o.total_amount for o in orders_qs)
    total_orders = orders_qs.count()
    pending_orders = Order.objects.filter(status='pending').count()
    recent_sales = sum(
        o.total_amount for o in orders_qs.filter(created_at__gte=last_30_days)
    )

    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]

    low_stock_variants = ProductVariant.objects.filter(
        stock_quantity__lte=10, stock_quantity__gt=0
    ).select_related('product').order_by('stock_quantity')[:8]

    out_of_stock_count = ProductVariant.objects.filter(stock_quantity=0).count()

    top_products = (
        OrderItem.objects.values('variant__product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    context.update({
        "kpi": [
            {"title": "Total Sales", "metric": f"৳{total_sales:,.0f}", "footer": "All confirmed orders"},
            {"title": "Total Orders", "metric": total_orders, "footer": "All time"},
            {"title": "Pending Orders", "metric": pending_orders, "footer": "Awaiting confirmation"},
            {"title": "Sales (30 days)", "metric": f"৳{recent_sales:,.0f}", "footer": "Last 30 days"},
        ],
        "recent_orders": recent_orders,
        "low_stock_variants": low_stock_variants,
        "out_of_stock_count": out_of_stock_count,
        "top_products": top_products,
    })

    return context