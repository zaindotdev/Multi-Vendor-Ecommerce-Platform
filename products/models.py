from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class TimeStampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children'
    )

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(TimeStampModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    vendor = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='products'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        return self.variants.aggregate(
            total=models.Sum('stock')
        )['total'] or 0


class ProductVariant(TimeStampModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )
    sku = models.CharField(max_length=100, unique=True)
    variant_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} — {self.variant_name}"


class ProductImage(TimeStampModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images'
    )
    image_url = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"Image for {self.product.name}"


class Review(TimeStampModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reviews'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='reviews'
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, null=True)

    class Meta:
        # One review per user per product
        unique_together = ('product', 'user')

    def __str__(self):
        return f"Review by {self.user.username} for {self.product.name}"