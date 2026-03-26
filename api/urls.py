from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from accounts.views import UserViewSet, AddressViewSet, VendorProfileViewSet, CustomerProfileViewSet
from products.views import CategoryViewSet, ProductViewSet, ProductVariantViewSet, ProductImageViewSet, ReviewViewSet
from orders.views import CartViewSet, CartItemViewSet, OrderViewSet, OrderItemViewSet

router = DefaultRouter()

router.register(r'users', UserViewSet, basename='user')
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'vendors', VendorProfileViewSet, basename='vendor')
router.register(r'customers', CustomerProfileViewSet, basename='customer')

router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')
router.register(r'images', ProductImageViewSet, basename='product-image')
router.register(r'reviews', ReviewViewSet, basename='review')

router.register(r'cart', CartViewSet, basename='cart')
router.register(r'cart-items', CartItemViewSet, basename='cart-item')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='order-item')

urlpatterns = [
    path('', include(router.urls)),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
]
