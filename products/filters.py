from __future__ import annotations

import django_filters
from django.db.models import Avg, Exists, OuterRef, Q, QuerySet

from .models import Product, ProductVariant, Category


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(method="filter_category")
    category__slug = django_filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    vendor = django_filters.NumberFilter(field_name="vendor")
    min_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(method="filter_min_rating", label="Minimum rating")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock", label="In stock")
    search = django_filters.CharFilter(method="filter_search", label="Search")
    ordering = django_filters.OrderingFilter(
        fields=(
            ("base_price", "price"),
            ("base_price", "base_price"),
            ("created_at", "created_at"),
            ("avg_rating", "rating"),
        )
    )

    class Meta:
        model = Product
        fields = {
            "category": ["exact"],
            "category__slug": ["exact"],
            "vendor": ["exact"],
        }

    def filter_category(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        if value.isdigit():
            return queryset.filter(category_id=int(value))
        return queryset.filter(Q(category__slug__iexact=value) | Q(category__name__iexact=value))

    def filter_min_rating(self, queryset: QuerySet[Product], name: str, value: float) -> QuerySet[Product]:
        return queryset.annotate(avg_rating=Avg("reviews__rating")).filter(avg_rating__gte=value)

    def filter_in_stock(self, queryset: QuerySet[Product], name: str, value: bool) -> QuerySet[Product]:
        variant_in_stock = ProductVariant.objects.filter(product=OuterRef("pk"), stock__gt=0)
        queryset = queryset.annotate(has_stock=Exists(variant_in_stock))
        return queryset.filter(has_stock=value)

    def filter_search(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value)).distinct()

class CategoryFilter(django_filters.FilterSet):
    parent = django_filters.NumberFilter(field_name="parent__id")
    parent_slug = django_filters.CharFilter(field_name="parent__slug")

    class Meta:
        model = Category
        fields = ["parent", "parent_slug"]