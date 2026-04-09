from django.db.models import Avg, Count, Q
from rest_framework import serializers

from orders.models import Order, OrderItem
from .models import Category, Product, ProductImage, ProductVariant, Review
import uuid
from django.utils.text import slugify


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
    sku = serializers.CharField(required=False, allow_blank=True, read_only=True)
    class Meta:
        model = ProductVariant
        fields = ['id', 'product', 'sku', 'variant_name', 'price', 'stock', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_sku(self, value):
        if not value:
            return str(uuid.uuid4())
        return value

    def create(self, validated_data):
        if not validated_data.get('sku'):
            validated_data['sku'] = str(uuid.uuid4())
        return super().create(validated_data)

class ProductListSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    vendor_shop_name = serializers.SerializerMethodField()
    url = serializers.HyperlinkedIdentityField(view_name='product-detail', lookup_field='slug')

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'base_price', 'thumbnail', 'average_rating', 'vendor_shop_name', 'url']

    def get_thumbnail(self, obj) -> str | None:
        primary = next((img for img in obj.images.all() if img.is_primary), None)
        image = primary or obj.images.all().first()
        if not image or not image.image_url:
            return None
        try:
            request = self.context.get('request')
            return request.build_absolute_uri(image.image_url.url) if request else image.image_url.url
        except Exception:
            return None

    def get_average_rating(self, obj) -> float:
        avg = getattr(obj, 'avg_rating', None)
        if avg is not None:
            return round(float(avg), 2)
        return round(float(obj.reviews.aggregate(avg=Avg('rating'))['avg'] or 0), 2)

    def get_vendor_shop_name(self, obj) -> str:
        profile = getattr(obj.vendor, 'vendor_profile', None)
        return profile.company_name if profile else obj.vendor.username


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

        eligible_statuses = [
            Order.Status.CONFIRMED,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ]
        has_purchase = OrderItem.objects.filter(
            order__user=request.user,
            product_variant__product=product,
        ).filter(
            Q(order__status__in=eligible_statuses)
            | Q(order__payment_status=Order.PaymentStatus.PAID)
        ).exists()
        if not has_purchase:
            raise serializers.ValidationError(
                'Only buyers with a verified purchase can review this product. '
                'The order must be paid or in confirmed/shipped/delivered status.'
            )

        already_reviewed_qs = Review.objects.filter(product=product, user=request.user)
        if self.instance is not None:
            already_reviewed_qs = already_reviewed_qs.exclude(pk=self.instance.pk)

        already_reviewed = already_reviewed_qs.exists()
        if already_reviewed:
            raise serializers.ValidationError('You have already reviewed this product.')

        return attrs


class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = serializers.SerializerMethodField()
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

    def get_images(self, obj) -> list:
        # Pass request context into nested serializer so image URLs resolve correctly
        return ProductImageSerializer(
            obj.images.all(),
            many=True,
            context=self.context,   # ← this is the key line
        ).data

    def get_average_rating(self, obj) -> float:
        return round(float(obj.reviews.aggregate(avg=Avg('rating'))['avg'] or 0), 2)

    def get_reviews_count(self, obj) -> int:
        return obj.reviews.count()

    def get_vendor(self, obj) -> dict:
        profile = getattr(obj.vendor, 'vendor_profile', None)
        logo = None
        if profile and profile.logo_url:
            try:
                request = self.context.get('request')
                logo = request.build_absolute_uri(profile.logo_url.url) if request else profile.logo_url.url
            except Exception:
                pass
        return {
            'id': obj.vendor.id,
            'username': obj.vendor.username,
            'company_name': profile.company_name if profile else None,
            'company_slug': profile.company_slug if profile else None,
            'logo': logo,
        }


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'base_price', 'category', 'is_active']
        read_only_fields = ['id']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if instance and instance.vendor_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only update your own products.')
        return attrs

    def create(self, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        return super().create(validated_data)


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