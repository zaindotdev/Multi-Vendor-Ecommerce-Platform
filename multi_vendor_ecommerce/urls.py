from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.conf import settings
from django.conf.urls.static import  static

from accounts.views import (
    VerifyEmailView, UserViewSet, AddressViewSet,
    VendorProfileViewSet, CustomerProfileViewSet,
)
from products.views import (
    CategoryViewSet, ProductViewSet, ReviewViewSet,
    ProductVariantViewSet, ProductImageViewSet,
)
from orders.views import (
    CartViewSet, CartItemViewSet, OrderViewSet, OrderItemViewSet,
    ShipmentViewSet, PaymentViewSet, CommissionViewSet, PayoutViewSet,
    StripeWebhookView,
)

router = routers.DefaultRouter()
router.register(r'cart',     CartViewSet,    basename='cart')
router.register(r'orders',   OrderViewSet,   basename='order')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'payouts',  PayoutViewSet,  basename='payout')

router.register(r'users', UserViewSet, basename='user')
router.register(r'addresses',  AddressViewSet,         basename='address')
router.register(r'vendors',    VendorProfileViewSet,   basename='vendor')
router.register(r'customers',  CustomerProfileViewSet, basename='customer')
router.register(r'categories',       CategoryViewSet,       basename='category')
router.register(r'products',         ProductViewSet,        basename='product')
router.register(r'product-variants', ProductVariantViewSet, basename='product-variant')
router.register(r'product-images',   ProductImageViewSet,   basename='product-image')
router.register(r'reviews',          ReviewViewSet,         basename='review')
router.register(r'cart-items',  CartItemViewSet,   basename='cart-item')
router.register(r'order-items', OrderItemViewSet,  basename='order-item')
router.register(r'shipments',   ShipmentViewSet,   basename='shipment')
router.register(r'commissions', CommissionViewSet, basename='commission')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/payments/stripe-webhook/', csrf_exempt(StripeWebhookView.as_view()), name='stripe-webhook'),
    path(
        'api/orders/payments/create-intent/',
        PaymentViewSet.as_view({'post': 'create_payment_intent'}),
        name='order-payment-create-intent',
    ),
    path('api/', include(router.urls)),
    path('api/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('api/token/',         TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(),   name='token_refresh'),
    path('', include('rest_framework.urls')),
    path('api/schema/', SpectacularAPIView.as_view(),                      name='schema'),
    path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',  SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)