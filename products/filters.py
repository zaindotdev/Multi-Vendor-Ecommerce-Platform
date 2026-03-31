from __future__ import annotations

import django_filters
from django.db.models import Exists, OuterRef, Q, QuerySet

from .models import Product, ProductVariant, Category


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(method='filter_category')
    vendor = django_filters.NumberFilter(field_name='vendor')
    min_price = django_filters.NumberFilter(field_name='base_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='base_price', lookup_expr='lte')
    min_rating = django_filters.NumberFilter(method='filter_min_rating', label='Minimum rating')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock', label='In stock')

    class Meta:
        model = Product
        fields: list = []

    def filter_category(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        if value.isdigit():
            return queryset.filter(category_id=int(value))
        return queryset.filter(Q(category__slug__iexact=value) | Q(category__name__iexact=value))

    def filter_min_rating(self, queryset: QuerySet[Product], name: str, value: float) -> QuerySet[Product]:
        return queryset.filter(avg_rating__gte=value)

    def filter_in_stock(self, queryset: QuerySet[Product], name: str, value: bool) -> QuerySet[Product]:
        variant_in_stock = ProductVariant.objects.filter(product=OuterRef('pk'), stock__gt=0)
        return queryset.annotate(has_stock=Exists(variant_in_stock)).filter(has_stock=value)


class CategoryFilter(django_filters.FilterSet):
    parent = django_filters.NumberFilter(field_name='parent__id')
    parent_slug = django_filters.CharFilter(field_name='parent__slug')

    class Meta:
        model = Category
        fields: list = []