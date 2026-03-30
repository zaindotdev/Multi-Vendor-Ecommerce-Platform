from __future__ import annotations

from django.db.models import Avg
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .filters import ProductFilter, CategoryFilter
from .pagination import StandardPagination, ProductPagination
from .models import Category, Product, ProductVariant, ProductImage, Review
from .permissions import IsProductOwner
from .serializers import (
    CategorySerializer,
    ProductImageSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    ReviewSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related("parent")
    serializer_class = CategorySerializer
    lookup_field = "slug"

    pagination_class = StandardPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ["name"]
    ordering_fields = ["created_at", "name"]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    lookup_field = "slug"

    pagination_class = ProductPagination

    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter

    search_fields = ["name", "description"]
    ordering_fields = ["base_price", "created_at"]

    def get_queryset(self):
        return (
            Product.objects.select_related("vendor", "category")
            .prefetch_related("variants", "images", "reviews")
            .annotate(avg_rating=Avg("reviews__rating"))
        )

    def perform_create(self, serializer) -> None:
        serializer.save(vendor=self.request.user)


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.select_related("product", "product__vendor")
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]

    pagination_class = StandardPagination


class ProductImageViewSet(viewsets.ModelViewSet):

    queryset = ProductImage.objects.select_related("product", "product__vendor")
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsProductOwner]

    pagination_class = StandardPagination


class ReviewViewSet(viewsets.ModelViewSet):

    queryset = Review.objects.select_related("product", "user")
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = StandardPagination