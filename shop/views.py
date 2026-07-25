from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .filters import ProductFilter
from rest_framework.pagination import PageNumberPagination

from sslcommerz_lib import SSLCOMMERZ
from django.conf import settings

from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    Cart, CartItem, Coupon, Order, OrderItem, Payment,
    Review, Wishlist
)
from .serializers import (
    RegisterSerializer, UserProfileSerializer, AddressSerializer, CategorySerializer,
    BrandSerializer, TagSerializer, ProductSerializer,
    CartSerializer, CartItemSerializer, CouponSerializer,
    OrderSerializer, PaymentSerializer, ReviewSerializer,
    WishlistSerializer
)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(parent=None)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['base_price', 'created_at']
    pagination_class = ProductPagination

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = serializer.validated_data['variant']
        quantity = serializer.validated_data.get('quantity', 1)

        item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item_id = request.data.get('item_id')
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def update_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item_id = request.data.get('item_id')
        quantity = request.data.get('quantity')
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.quantity = quantity
        item.save()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        if not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        for item in cart.items.all():
            if item.variant.stock_quantity < item.quantity:
                return Response(
                    {"error": f"Insufficient stock for {item.variant}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        total_amount = sum(item.variant.price * item.quantity for item in cart.items.all())
        order = serializer.save(
            user=request.user,
            order_number=f"ORD-{Order.objects.count() + 1:06d}",
            total_amount=total_amount
        )

        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price_at_purchase=item.variant.price
            )

        cart.items.all().delete()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def apply_coupon(self, request, pk=None):
        order = self.get_object()
        coupon_code = request.data.get('coupon_code')
        result = order.apply_coupon(coupon_code)
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in ['delivered', 'shipped']:
            return Response({"error": "Cannot cancel this order"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'cancelled'
        order.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(order__user=self.request.user)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        qs = Review.objects.all()
        if product_id:
            qs = qs.filter(product__id=product_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


#--------------Payment getway--------------------------------------------------
class InitiatePaymentView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)

        settings_dict = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_pass': settings.SSLCOMMERZ_STORE_PASSWORD,
            'issandbox': settings.SSLCOMMERZ_IS_SANDBOX,
        }
        sslcz = SSLCOMMERZ(settings_dict)

        post_body = {
            'total_amount': str(order.total_amount),
            'currency': 'BDT',
            'tran_id': order.order_number,
            'success_url': f'http://127.0.0.1:8000/api/shop/payment/success/{order.id}/',
            'fail_url': f'http://127.0.0.1:8000/api/shop/payment/fail/{order.id}/',
            'cancel_url': f'http://127.0.0.1:8000/api/shop/payment/cancel/{order.id}/',
            'emi_option': 0,
            'cus_name': request.user.username,
            'cus_email': request.user.email or 'test@example.com',
            'cus_phone': '01700000000',
            'cus_add1': 'Dhaka',
            'cus_city': 'Dhaka',
            'cus_country': 'Bangladesh',
            'shipping_method': 'NO',
            'num_of_item': order.items.count(),
            'product_name': 'Order Items',
            'product_category': 'Clothing',
            'product_profile': 'general',
        }

        response = sslcz.createSession(post_body)

        Payment.objects.update_or_create(
            order=order,
            defaults={'method': 'card', 'status': 'pending'}
        )

        return Response({'payment_url': response.get('GatewayPageURL')}, status=status.HTTP_200_OK)


class PaymentSuccessView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        order.status = 'confirmed'
        order.save()

        payment = order.payment
        payment.status = 'paid'
        payment.transaction_id = request.data.get('tran_id', '')
        payment.save()

        return Response({'message': 'Payment successful'}, status=status.HTTP_200_OK)


class PaymentFailView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        payment = order.payment
        payment.status = 'failed'
        payment.save()

        return Response({'message': 'Payment failed'}, status=status.HTTP_400_BAD_REQUEST)