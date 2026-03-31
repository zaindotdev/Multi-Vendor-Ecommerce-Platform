from django.contrib import admin
from django.db.models import Avg

from .models import Category, Product, ProductVariant, ProductImage, Review


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('variant_name', 'sku', 'price', 'stock')


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('image_url', 'alt_text', 'is_primary', 'display_order')


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ('user', 'rating', 'comment', 'created_at')
    readonly_fields = ('user', 'rating', 'comment', 'created_at')
    can_delete = False


class SubCategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    fields = ('name', 'slug')
    fk_name = 'parent'
    verbose_name = 'subcategory'
    verbose_name_plural = 'subcategories'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('parent',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubCategoryInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_username', 'vendor_shop_name', 'category', 'base_price', 'is_active', 'average_rating', 'created_at')
    search_fields = ('name', 'slug', 'vendor__username')
    list_filter = ('is_active', 'category')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductVariantInline, ProductImageInline, ReviewInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('vendor', 'vendor__vendor_profile', 'category').annotate(
            avg_rating=Avg('reviews__rating')
        )

    @admin.display(ordering='vendor__username', description='Vendor username')
    def vendor_username(self, obj):
        return obj.vendor.username

    @admin.display(description='Shop name')
    def vendor_shop_name(self, obj):
        profile = getattr(obj.vendor, 'vendor_profile', None)
        return profile.company_name if profile else '—'

    @admin.display(ordering='avg_rating', description='Avg rating')
    def average_rating(self, obj):
        avg = getattr(obj, 'avg_rating', None)
        return round(float(avg), 2) if avg is not None else '—'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('product__name', 'user__username')
    readonly_fields = ('product', 'user', 'rating', 'comment', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False