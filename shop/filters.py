import django_filters
from .models import Product
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

    class Meta:
        model = Product
        fields = ['category', 'brand', 'min_price', 'max_price', 'search']


# class ProductFilter(django_filters.FilterSet):
#     class Meta:
#         model = Product
#         fields = {
#             'base_price': ['gte', 'lte'],  # min_price, max_price
#             'category__slug': ['exact'],   # category
#             'brand__id': ['exact'],        # brand
#         }