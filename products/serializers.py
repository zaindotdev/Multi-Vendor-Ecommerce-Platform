from django.db.models import Avg, Count
from rest_framework import serializers

from orders.models import OrderItem
from .models import Category, Product, ProductImage, ProductVariant, Review


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'children', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.all()
        return CategorySerializer(children, many=True, context=self.context).data


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


class ProductListSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    vendor_shop_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'base_price', 'thumbnail', 'average_rating', 'vendor_shop_name']

    def get_thumbnail(self, obj):
        primary = next((img for img in obj.images.all() if img.is_primary), None)
        if primary:
            return primary.image_url
        first = obj.images.all().first()
        return first.image_url if first else None

    def get_average_rating(self, obj):
        avg = getattr(obj, 'avg_rating', None)
        if avg is not None:
            return round(float(avg), 2)
        return round(float(obj.reviews.aggregate(avg=Avg('rating'))['avg'] or 0), 2)

    def get_vendor_shop_name(self, obj):
        profile = getattr(obj.vendor, 'vendor_profile', None)
        if profile:
            return profile.company_name
        return obj.vendor.username


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'product', 'user', 'user_name', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return obj.user.username

    def validate(self, attrs):
        request = self.context['request']
        product = attrs['product']

        if product.vendor_id == request.user.id:
            raise serializers.ValidationError('Vendors cannot review their own products.')

        has_purchase = OrderItem.objects.filter(
            order__user=request.user,
            order__status__in=['confirmed', 'shipped', 'delivered'],
            product_variant__product=product,
        ).exists()
        if not has_purchase:
            raise serializers.ValidationError('Only buyers with a verified purchase can review this product.')

        # Enforce uniqueness manually because user is injected in perform_create, not in attrs.
        already_reviewed = Review.objects.filter(product=product, user=request.user).exists()
        if already_reviewed:
            raise serializers.ValidationError('You have already reviewed this product.')

        return attrs


class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'base_price', 'category', 'is_active',
            'vendor', 'variants', 'images', 'reviews', 'average_rating', 'reviews_count',
            'created_at', 'updated_at',
        ]

    def get_average_rating(self, obj):
        return round(float(obj.reviews.aggregate(avg=Avg('rating'))['avg'] or 0), 2)

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_vendor(self, obj):
        profile = getattr(obj.vendor, 'vendor_profile', None)
        return {
            'id': obj.vendor.id,
            'username': obj.vendor.username,
            'company_name': profile.company_name if profile else None,
            'company_slug': profile.company_slug if profile else None,
        }


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'base_price', 'category', 'is_active']
        read_only_fields = ['id']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if instance and instance.vendor_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only update your own products.')
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'base_price', 'vendor', 'category', 'is_active',
            'average_rating', 'reviews_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        avg = getattr(obj, 'avg_rating', None)
        if avg is not None:
            return round(float(avg), 2)
        return round(float(obj.reviews.aggregate(avg=Avg('rating'))['avg'] or 0), 2)

    def get_reviews_count(self, obj):
        count = getattr(obj, 'reviews_count_annotated', None)
        if count is not None:
            return int(count)
        return int(obj.reviews.aggregate(total=Count('id'))['total'] or 0)