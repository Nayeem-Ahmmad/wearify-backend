from django.utils import timezone
from django.db.models import Sum, Count, Min
from django.db.models.functions import TruncDate
from datetime import timedelta
import json
from .models import Order, ProductVariant, OrderItem, Payment, Cart


def dashboard_callback(request, context):
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    orders_qs = Order.objects.exclude(status='cancelled')

    total_sales = sum(o.total_amount for o in orders_qs)
    total_orders = orders_qs.count()
    pending_orders = Order.objects.filter(status='pending').count()
    recent_sales = sum(o.total_amount for o in orders_qs.filter(created_at__gte=last_30_days))
    aov = (total_sales / total_orders) if total_orders else 0

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

    daily_sales = (
        orders_qs.filter(created_at__gte=last_30_days)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('total_amount'))
        .order_by('day')
    )
    sales_by_day = {row['day']: float(row['total']) for row in daily_sales}
    chart_labels, chart_values = [], []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).date()
        chart_labels.append(day.strftime('%b %d'))
        chart_values.append(sales_by_day.get(day, 0))

    recent_order_user_ids = orders_qs.filter(created_at__gte=last_30_days).values_list('user_id', flat=True).distinct()
    new_customers = 0
    returning_customers = 0
    for user_id in recent_order_user_ids:
        first_order_date = Order.objects.filter(user_id=user_id).aggregate(first=Min('created_at'))['first']
        if first_order_date and first_order_date >= last_30_days:
            new_customers += 1
        else:
            returning_customers += 1

    payment_counts = Payment.objects.values('status').annotate(count=Count('id'))
    payment_breakdown = {row['status']: row['count'] for row in payment_counts}

    abandoned_carts = Cart.objects.filter(items__isnull=False).distinct()
    abandoned_cart_count = abandoned_carts.count()
    abandoned_cart_value = sum(
        item.variant.price * item.quantity
        for cart in abandoned_carts
        for item in cart.items.all()
    )

    context.update({
        "kpi": [
            {"title": "Total Sales", "metric": f"৳{total_sales:,.0f}", "footer": "All confirmed orders"},
            {"title": "Total Orders", "metric": total_orders, "footer": "All time"},
            {"title": "Avg. Order Value", "metric": f"৳{aov:,.0f}", "footer": "Per order"},
            {"title": "Pending Orders", "metric": pending_orders, "footer": "Awaiting confirmation"},
            {"title": "Sales (30 days)", "metric": f"৳{recent_sales:,.0f}", "footer": "Last 30 days"},
        ],
        "recent_orders": recent_orders,
        "low_stock_variants": low_stock_variants,
        "out_of_stock_count": out_of_stock_count,
        "top_products": top_products,
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
        "new_customers": new_customers,
        "returning_customers": returning_customers,
        "payment_paid": payment_breakdown.get('paid', 0),
        "payment_pending": payment_breakdown.get('pending', 0),
        "payment_failed": payment_breakdown.get('failed', 0),
        "abandoned_cart_count": abandoned_cart_count,
        "abandoned_cart_value": f"৳{abandoned_cart_value:,.0f}",
    })

    return context