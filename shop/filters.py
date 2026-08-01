import django_filters
from .models import Product
from django.db.models import F
class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='base_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='base_price', lookup_expr='lte')

    category = django_filters.CharFilter(
        field_name='category__slug',
        lookup_expr='exact'
    )

    brand = django_filters.CharFilter(
        field_name='brand__name',
        lookup_expr='icontains'
    )

    search = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )

    on_sale = django_filters.BooleanFilter(method='filter_on_sale')

    def filter_on_sale(self, queryset, name, value):
        if value:
            return queryset.filter(
                variants__price_override__isnull=False,
                variants__price_override__lt=F('base_price'),
            ).distinct()
        return queryset

    class Meta:
        model = Product
        fields = ['category', 'brand', 'min_price', 'max_price', 'search', 'on_sale']


# class ProductFilter(django_filters.FilterSet):
#     class Meta:
#         model = Product
#         fields = {
#             'base_price': ['gte', 'lte'],  # min_price, max_price
#             'category__slug': ['exact'],   # category
#             'brand__id': ['exact'],        # brand
#         }