from __future__ import annotations

from django.db.models import Avg
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser, IsAuthenticated, IsAuthenticatedOrReadOnly

from .filters import CategoryFilter, ProductFilter
from .models import Category, Product, ProductImage, ProductVariant, Review
from .pagination import ProductPagination, StandardPagination
from .permissions import IsAdminUser as IsVendorAdminUser, IsProductOwner
from .serializers import (
    CategorySerializer,
    ProductCreateUpdateSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ReviewSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('parent').prefetch_related('children')
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ['name']
    ordering_fields = ['created_at', 'name']

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy'}:
            return [IsAuthenticated(), IsVendorAdminUser()]
        return []


class ProductViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    pagination_class = ProductPagination
    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['base_price', 'created_at', 'avg_rating']

    def get_queryset(self):
        return (
            Product.objects
            .select_related('vendor', 'vendor__vendor_profile', 'category')
            .prefetch_related('variants', 'images', 'reviews__user')
            .annotate(avg_rating=Avg('reviews__rating'))
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        if self.action == 'retrieve':
            return ProductDetailSerializer
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductCreateUpdateSerializer
        return ProductListSerializer

    def perform_create(self, serializer) -> None:
        serializer.save(vendor=self.request.user)


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.select_related('product', 'product__vendor')
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]
    pagination_class = StandardPagination


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related('product', 'product__vendor')
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]
    pagination_class = StandardPagination


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Review.objects.select_related('product', 'user')
        if self.action in {'destroy', 'update', 'partial_update'}:
            user = self.request.user
            if getattr(user, 'role', None) != 'admin':
                return qs.filter(user=user)
        return qs

    def perform_create(self, serializer) -> None:
        serializer.save(user=self.request.user)