from rest_framework import serializers
from .models import Category, Product, ProductVariant, ProductImage, Review


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image_url', 'alt_text', 'is_primary', 'display_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'product', 'sku', 'variant_name', 'price', 'stock', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'user', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'base_price', 'vendor', 'category', 'is_active', 'variants', 'images', 'reviews', 'created_at', 'updated_at']
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']
