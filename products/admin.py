from django.contrib import admin
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
    list_display = ('name', 'vendor', 'category', 'base_price', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'vendor__username')
    list_filter = ('is_active', 'category')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductVariantInline, ProductImageInline, ReviewInline]

