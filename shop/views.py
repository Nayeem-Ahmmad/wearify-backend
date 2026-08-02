from xml.dom import ValidationErr

from django.utils import timezone
from rest_framework import viewsets, generics, status, permissions
from rest_framework.views import APIView
from django.utils.timezone import now
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404, redirect
from rest_framework.response import Response
from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .filters import ProductFilter
from django.urls import reverse
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import AnonRateThrottle
from .tasks import send_payment_success_email_task, send_contact_message_task
from rest_framework.exceptions import NotFound


import logging
logger = logging.getLogger(__name__)
from sslcommerz_lib import SSLCOMMERZ, sslcommerz
from django.conf import settings
from django.core.mail import send_mail
from rest_framework import generics

from django.db.models import F

from .models import (
    UserProfile, Address, Category, Brand, Tag, Product,
    Cart, CartItem, Coupon, Order, OrderItem, Payment,
    Review, Wishlist, FlashSale
)
from .serializers import (
    RegisterSerializer, UserProfileSerializer, AddressSerializer, CategorySerializer,
    BrandSerializer, TagSerializer, ProductSerializer,
    CartSerializer, CartItemSerializer, CouponSerializer,
    OrderSerializer, PaymentSerializer, ReviewSerializer,
    WishlistSerializer, UserAccountUpdateSerializer, ContactMessageSerializer, FlashSaleSerializer, FlashSaleDetailSerializer
)

class RegisterThrottle(AnonRateThrottle):
    scope = 'register'


class ActiveFlashSaleView(generics.RetrieveAPIView):
    serializer_class = FlashSaleDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        now = timezone.now()
        flash_sale = FlashSale.objects.filter(
            start_time__lte=now,
            end_time__gte=now
        ).prefetch_related('products').first()
        if not flash_sale:
            raise NotFound("No active flash sale")
        return flash_sale


class ContactMessageView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        send_contact_message_task.delay(data['name'], data['email'], data['message'])
        return Response(
            {"success": "Your message has been received. We'll get back to you soon!"},
            status=status.HTTP_200_OK
        )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterThrottle]

class UpdateAccountView(generics.UpdateAPIView):
    serializer_class = UserAccountUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
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

    @action(detail=True, methods=['get'])
    def related(self, request, slug=None):
        product = self.get_object()
        related_products = product.get_related_products()
        serializer = ProductSerializer(related_products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def deals(self, request):
        from django.utils import timezone
        from django.db.models import Q, F
        now = timezone.now()
        flash_sale_q = Q(flash_sales__start_time__lte=now, flash_sales__end_time__gte=now)
        override_q = Q(variants__price_override__isnull=False, variants__price_override__lt=F('base_price'))
        queryset = self.filter_queryset(
            self.get_queryset().filter(is_active=True).filter(flash_sale_q | override_q).distinct()
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

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
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        variant = serializer.validated_data['variant']
        quantity = serializer.validated_data.get('quantity', 1)

        item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()

        return Response(CartSerializer(cart, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item_id = request.data.get('item_id')
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        return Response(CartSerializer(cart, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def update_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item_id = request.data.get('item_id')
        quantity = request.data.get('quantity')
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.quantity = quantity
        item.save()
        return Response(CartSerializer(cart, context={'request': request}).data, status=status.HTTP_200_OK)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item_ids = request.data.get('item_ids')

        if item_ids:
            items_qs = cart.items.filter(id__in=item_ids)
        else:
            items_qs = cart.items.all()

        if not items_qs.exists():
            logger.warning(f"Order creation failed - no items selected for user {request.user.username}")
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        for item in items_qs:
            if item.variant.stock_quantity < item.quantity:
                logger.warning(f"Order creation failed - insufficient stock for {item.variant} (user: {request.user.username})")
                return Response(
                    {"error": f"Insufficient stock for {item.variant}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        delivery_location = request.data.get('delivery_location', 'inside_dhaka')
        items_total = sum(item.variant.price * item.quantity for item in items_qs)

        if items_total > 2500:
            shipping_cost = 0
        else:
            shipping_cost = 60 if delivery_location == 'inside_dhaka' else 130

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        total_amount = items_total + shipping_cost

        order = serializer.save(
            user=request.user,
            order_number=f"ORD-{Order.objects.count() + 1:06d}",
            total_amount=total_amount,
            shipping_cost=shipping_cost
        )

        for item in items_qs:
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price_at_purchase=item.variant.price
            )

        items_qs.delete()
        logger.info(f"Order {order.order_number} created successfully by {request.user.username}")
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
        if order.status != 'pending':
            return Response({"error": "This order can no longer be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
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



#--------------- Payment Getway -------------------------------------------------
class InitiatePaymentView(generics.GenericAPIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        order = self._get_validated_order(order_id, request.user)

        validation_error = self._validate_order_payable(order)
        if validation_error:
            return validation_error

        customer_data = self._get_customer_data(request, order)
        if isinstance(customer_data, Response):
            return customer_data

        post_body = self._prepare_sslcommerz_payload(order, request, customer_data)
        sslcz = self._get_sslcommerz_client()

        try:
            response = sslcz.createSession(post_body)
        except Exception as e:
            logger.error(f"SSLCOMMERZ session creation failed: {str(e)}")
            return Response(
                {"error": "Payment gateway is temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        logger.error(f"SSLCOMMERZ raw response: {response}")

        if not response or response.get('status') != 'SUCCESS' or not response.get('GatewayPageURL'):
            logger.error(f"SSLCOMMERZ invalid response: {response}")
            return Response(
                {
                    "error": "Failed to initiate payment. Please try again.",
                    "gateway_response": response
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        self._create_payment_record(order, request)

        return Response({
            'payment_url': response.get('GatewayPageURL'),
            'order_id': order.id,
            'transaction_id': order.order_number
        }, status=status.HTTP_200_OK)

    def _get_validated_order(self, order_id, user):
        return get_object_or_404(Order, id=order_id, user=user)

    def _validate_order_payable(self, order):
        if order.status in ['paid', 'shipped', 'delivered']:
            return Response(
                {"error": "This order has already been processed."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.status == 'cancelled':
            return Response(
                {"error": "This order has been cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.total_amount <= 0:
            return Response(
                {"error": "Invalid order amount."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return None

    def _get_customer_data(self, request, order):
        phone = request.data.get('phone_number')

        if not phone and order.shipping_address:
            phone = order.shipping_address.phone

        if not phone and hasattr(request.user, 'profile'):
            phone = request.user.profile.phone

        if not phone:
            return Response(
                {"error": "Phone number is required for payment. Please add a phone number to your profile or shipping address."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return {
            'phone': phone,
            'address': order.shipping_address,
            'email': request.user.email or 'customer@example.com',
            'name': request.user.get_full_name() or request.user.username
        }

    def _prepare_sslcommerz_payload(self, order, request, customer_data):
        base_url = self._get_base_url(request)

        success_url = f"{base_url}{reverse('payment-success', kwargs={'order_id': order.id})}"
        fail_url = f"{base_url}{reverse('payment-fail', kwargs={'order_id': order.id})}"
        cancel_url = f"{base_url}{reverse('payment-cancel', kwargs={'order_id': order.id})}"

        product_names = self._get_product_names(order)
        total_items = self._get_total_items(order)
        address = customer_data['address']

        payload = {
            'total_amount': str(order.total_amount),
            'currency': 'BDT',
            'tran_id': order.order_number,
            'success_url': success_url,
            'fail_url': fail_url,
            'cancel_url': cancel_url,
            'emi_option': 0,
            'cus_name': customer_data['name'][:50],
            'cus_email': customer_data['email'][:50],
            'cus_phone': customer_data['phone'][:20],
            'cus_add1': self._get_address_line(address),
            'cus_city': 'Dhaka',
            'cus_country': 'Bangladesh',
            'shipping_method': 'YES' if order.shipping_address else 'NO',
            'num_of_item': total_items,
            'product_name': product_names[:100],
            'product_category': 'E-commerce',
            'product_profile': 'general',
        }

        if order.shipping_address:
            payload.update({
                'ship_name': customer_data['name'][:50],
                'ship_add1': self._get_address_line(address),
                'ship_city': 'Dhaka',
                'ship_postcode': '1000',
                'ship_country': 'Bangladesh',
            })

        return payload

    def _get_base_url(self, request):
        if getattr(settings, 'SITE_URL', None):
            return settings.SITE_URL
        protocol = 'https' if request.is_secure() else 'http'
        return f"{protocol}://{request.get_host()}"

    def _get_product_names(self, order):
        items = order.items.all()
        if not items:
            return "Order Items"
        names = [item.variant.product.name for item in items[:3]]
        product_names = ', '.join(names)
        if items.count() > 3:
            product_names += f" & {items.count() - 3} more"
        return product_names

    def _get_total_items(self, order):
        return sum(item.quantity for item in order.items.all())

    def _get_address_line(self, address):
        if not address:
            return 'N/A'
        return address.full_address or 'N/A'

    def _get_sslcommerz_client(self):
        settings_dict = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_pass': settings.SSLCOMMERZ_STORE_PASSWORD,
            'issandbox': settings.SSLCOMMERZ_IS_SANDBOX,
        }
        return SSLCOMMERZ(settings_dict)

    def _create_payment_record(self, order, request):
        method = request.data.get('payment_method', 'card')
        Payment.objects.update_or_create(
            order=order,
            defaults={
                'method': method,
                'status': 'pending',
                'transaction_id': order.order_number
            }
        )


class PaymentSuccessView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_id):
        return self._handle(request, order_id)

    def get(self, request, order_id):
        return self._handle(request, order_id)

    def _handle(self, request, order_id):
        from django.utils.timezone import now
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'paid'
            order.save()

            payment = Payment.objects.filter(order=order).first()
            if payment:
                card_type = (request.POST.get('card_type') or request.GET.get('card_type', '')).lower()
                payment.method = self._map_method(card_type)
                payment.status = 'paid'
                payment.transaction_id = request.POST.get('tran_id') or request.GET.get('tran_id', payment.transaction_id)
                payment.paid_at = now()
                payment.save()

            send_payment_success_email_task.delay(order.id)
            logger.info(f"Payment successful for order {order.order_number}")

            if getattr(settings, 'FRONTEND_URL', None):
                return redirect(f"{settings.FRONTEND_URL}/payment/success?order_id={order.id}")
            return Response({'message': 'Payment successful', 'order_id': order.id})

        except Order.DoesNotExist:
            logger.error(f"Payment success callback failed - order {order_id} not found")
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment success callback error for order {order_id}: {str(e)}")
            return Response({'error': 'Payment processing failed'}, status=status.HTTP_400_BAD_REQUEST)

    def _map_method(self, card_type):
        if 'bkash' in card_type:
            return 'bkash'
        if 'nagad' in card_type:
            return 'nagad'
        if 'cod' in card_type:
            return 'cod'
        return 'card'

class PaymentFailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_id):
        return self._handle(request, order_id)

    def get(self, request, order_id):
        return self._handle(request, order_id)

    def _handle(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            payment = Payment.objects.filter(order=order).first()
            if payment:
                payment.status = 'failed'
                payment.save()

            if getattr(settings, 'FRONTEND_URL', None):
                return redirect(f"{settings.FRONTEND_URL}/payment/fail?order_id={order.id}")
            return Response({'error': 'Payment failed', 'order_id': order.id})

        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment fail callback error: {str(e)}")
            return Response({'error': 'Payment processing failed'}, status=status.HTTP_400_BAD_REQUEST)


class PaymentCancelView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_id):
        return self._handle(request, order_id)

    def get(self, request, order_id):
        return self._handle(request, order_id)

    def _handle(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            payment = Payment.objects.filter(order=order).first()
            if payment:
                payment.status = 'cancelled'
                payment.save()

            if getattr(settings, 'FRONTEND_URL', None):
                return redirect(f"{settings.FRONTEND_URL}/payment/cancel?order_id={order.id}")
            return Response({'message': 'Payment cancelled', 'order_id': order.id})

        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment cancel callback error: {str(e)}")
            return Response({'error': 'Payment processing failed'}, status=status.HTTP_400_BAD_REQUEST)


class ActiveFlashSaleView(generics.RetrieveAPIView):
    serializer_class = FlashSaleDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        now = timezone.now()
        flash_sale = FlashSale.objects.filter(
            start_time__lte=now,
            end_time__gte=now
        ).prefetch_related('products').first()
        if not flash_sale:
            raise NotFound("No active flash sale")
        return flash_sale