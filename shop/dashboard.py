from django.utils import timezone
from django.db.models import Sum, Count, Min
from django.db.models.functions import TruncDate
from datetime import timedelta
import json
from .models import Order, ProductVariant, OrderItem, Payment, Cart
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models.functions import TruncDate, TruncMonth


def dashboard_callback(request, context):
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    orders_qs = Order.objects.exclude(status='cancelled')

    total_sales = sum(o.total_amount for o in orders_qs)
    total_orders = orders_qs.count()
    pending_orders = Order.objects.filter(status='pending').count()
    recent_sales = sum(o.total_amount for o in orders_qs.filter(created_at__gte=last_30_days))
    aov = (total_sales / total_orders) if total_orders else 0

    # Profit calculation — only counts orders that are confirmed or further along,
    # since 'pending' orders may still be cancelled and haven't actually sold yet.
    profit_orders_qs = Order.objects.exclude(status__in=['cancelled', 'pending'])
    profit_items = OrderItem.objects.filter(
        order__in=profit_orders_qs
    ).select_related('variant__product')

    total_profit = sum(
        (item.price_at_purchase - item.variant.product.cost_price) * item.quantity
        for item in profit_items if item.variant
    )
    recent_profit_items = OrderItem.objects.filter(
        order__in=profit_orders_qs, order__created_at__gte=last_30_days
    ).select_related('variant__product')
    recent_profit = sum(
        (item.price_at_purchase - item.variant.product.cost_price) * item.quantity
        for item in recent_profit_items if item.variant
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

    # Order status breakdown
    status_counts = Order.objects.exclude(status='cancelled').values('status').annotate(count=Count('id'))
    order_status_labels = [row['status'].capitalize() for row in status_counts]
    order_status_values = [row['count'] for row in status_counts]

    # Category-wise sales
    category_sales = (
        OrderItem.objects.filter(order__in=orders_qs)
        .values('variant__product__category__name')
        .annotate(total=Sum('price_at_purchase'))
        .order_by('-total')[:8]
    )
    category_labels = [row['variant__product__category__name'] or 'Uncategorized' for row in category_sales]
    category_values = [float(row['total'] or 0) for row in category_sales]

    # Revenue vs profit trend (reuses same 30-day window)
    daily_profit_items = (
        OrderItem.objects.filter(order__in=profit_orders_qs, order__created_at__gte=last_30_days)
        .select_related('variant__product')
        .annotate(day=TruncDate('order__created_at'))
    )
    profit_by_day = {}
    for item in daily_profit_items:
        if not item.variant:
            continue
        day = item.day
        profit = (item.price_at_purchase - item.variant.product.cost_price) * item.quantity
        profit_by_day[day] = profit_by_day.get(day, 0) + profit
    chart_profit_values = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).date()
        chart_profit_values.append(float(profit_by_day.get(day, 0)))

    # Top customers by spend
    top_customers = (
        orders_qs.values('user__username')
        .annotate(total_spent=Sum('total_amount'), order_count=Count('id'))
        .order_by('-total_spent')[:5]
    )

    # Review rating overview
    from .models import Review
    rating_counts = Review.objects.values('rating').annotate(count=Count('id')).order_by('rating')
    rating_by_star = {row['rating']: row['count'] for row in rating_counts}
    review_labels = [f"{i} ★" for i in range(1, 6)]
    review_values = [rating_by_star.get(i, 0) for i in range(1, 6)]
    total_reviews = sum(review_values)
    avg_rating = (sum(i * review_by_star for i, review_by_star in zip(range(1, 6), review_values)) / total_reviews) if total_reviews else 0

    context.update({
        "kpi": [
            {"title": "Total Sales", "metric": f"৳{total_sales:,.0f}", "footer": "All confirmed orders"},
            {"title": "Total Profit", "metric": f"৳{total_profit:,.0f}", "footer": "Confirmed & later orders"},
            {"title": "Total Orders", "metric": total_orders, "footer": "All time"},
            {"title": "Avg. Order Value", "metric": f"৳{aov:,.0f}", "footer": "Per order"},
            {"title": "Pending Orders", "metric": pending_orders, "footer": "Awaiting confirmation"},
            {"title": "Sales (30 days)", "metric": f"৳{recent_sales:,.0f}", "footer": "Last 30 days"},
            {"title": "Profit (30 days)", "metric": f"৳{recent_profit:,.0f}", "footer": "Last 30 days"},
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
        "order_status_labels": json.dumps(order_status_labels),
        "order_status_values": json.dumps(order_status_values),
        "category_labels": json.dumps(category_labels),
        "category_values": json.dumps(category_values),
        "chart_profit_values": json.dumps(chart_profit_values),
        "top_customers": top_customers,
        "review_labels": json.dumps(review_labels),
        "review_values": json.dumps(review_values),
        "avg_rating": f"{avg_rating:.1f}",
        "total_reviews": total_reviews,
    })

    return context

@staff_member_required
def monthly_sales_report(request):
    orders_qs = Order.objects.exclude(status='cancelled')

    monthly_orders = (
        orders_qs
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total_sales=Sum('total_amount'), order_count=Count('id'))
        .order_by('-month')
    )

    profit_orders_qs = Order.objects.exclude(status__in=['cancelled', 'pending'])
    profit_items = (
        OrderItem.objects.filter(order__in=profit_orders_qs)
        .annotate(month=TruncMonth('order__created_at'))
        .select_related('variant__product')
    )

    profit_by_month = {}
    for item in profit_items:
        if not item.variant:
            continue
        profit = (item.price_at_purchase - item.variant.product.cost_price) * item.quantity
        profit_by_month[item.month] = profit_by_month.get(item.month, 0) + profit

    rows = []
    for row in monthly_orders:
        month = row['month']
        total_sales = row['total_sales'] or 0
        order_count = row['order_count']
        avg_order = (total_sales / order_count) if order_count else 0
        rows.append({
            'month_label': month.strftime('%B %Y'),
            'total_sales': f"৳{total_sales:,.0f}",
            'profit': f"৳{profit_by_month.get(month, 0):,.0f}",
            'order_count': order_count,
            'avg_order': f"৳{avg_order:,.0f}",
        })

    return render(request, 'admin/monthly_sales.html', {'rows': rows})


@staff_member_required
def orders_report(request):
    orders = Order.objects.exclude(status='cancelled').select_related('user').order_by('-created_at')
    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin/orders_report.html', {'page_obj': page_obj})


@staff_member_required
def low_stock_report(request):
    variants = ProductVariant.objects.filter(stock_quantity__lte=10).select_related('product').order_by('stock_quantity')
    paginator = Paginator(variants, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin/low_stock_report.html', {'page_obj': page_obj})


@staff_member_required
def top_products_report(request):
    products = (
        OrderItem.objects.values('variant__product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')
    )
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin/top_products_report.html', {'page_obj': page_obj})