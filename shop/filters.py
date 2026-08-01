import django_filters
from .models import Product
from django.db.models import F
from django.db import models
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
            return queryset.filter(variants__price_override__isnull=False)
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




# kichu smossa 

# 1.logout obosthay kono user jkhn kono product, add to cart or buy now a click korbe tkhn tabe sign in page a niye jabe..currect a ai logic nai ata fix kro

# 2.jkhn phone version a jai..tkhn right side ar top corner a 3 line button kaj kore na fix kore dibe

# 3.kono customer jkhn amader sathe contact korbe tkhn tar sms jeno amader kache ase mane warify.sells ai mail a ase..seta fix kro

# 4.Flash Sale cart ar time ta start korbo kivabe..ata fix kore deo

# 5.kono user account profile ar photo ta aro boro kore dibe..akhn right side ar top corner a je choto kore user ar photo ta diye dibe..