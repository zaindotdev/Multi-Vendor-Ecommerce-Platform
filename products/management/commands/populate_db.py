from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from decimal import Decimal
import random
from pathlib import Path
from django.conf import settings

from products.models import Category, Product, ProductVariant, ProductImage, Review

User = get_user_model()


class Command(BaseCommand):
    help = "Populate database with sample products"

    def _fetch_placeholder(self, label: str) -> tuple[str, ContentFile]:
        slug = label.lower().replace(" ", "_")
        for ext in ("jpeg", "jpg", "png", "webp"):
            path = Path(settings.MEDIA_ROOT) / f"{slug}.{ext}"
            if path.exists():
                with open(path, "rb") as f:
                    return f"{slug}.{ext}", ContentFile(f.read(), name=f"{slug}.{ext}")
        raise FileNotFoundError(f"No image found for '{label}' in media dir")
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database population...")

        users = list(User.objects.all())
        if not users:
            self.stdout.write(self.style.ERROR("No users found. Create users first."))
            return

        vendors = users[:3] if len(users) >= 3 else users

        electronics, _ = Category.objects.get_or_create(name="Electronics", slug="electronics")
        phones, _      = Category.objects.get_or_create(name="Phones",  slug="phones",  parent=electronics)
        laptops, _     = Category.objects.get_or_create(name="Laptops", slug="laptops", parent=electronics)
        fashion, _     = Category.objects.get_or_create(name="Fashion", slug="fashion")
        shoes, _       = Category.objects.get_or_create(name="Shoes",   slug="shoes",   parent=fashion)
        categories     = [phones, laptops, shoes]
        self.stdout.write("Categories created.")

        product_names = [
            "iPhone 14",
            "Samsung Galaxy S23",
            "MacBook Pro",
            "Dell XPS 13",
            "Running Sneakers",
            "Air Max Shoes",
        ]

        variant_options = [
            ["64GB", "128GB", "256GB"],
            ["8GB RAM", "16GB RAM"],
            ["Red", "Blue", "Black"],
        ]

        products = []

        for name in product_names:
            slug = name.lower().replace(" ", "-")

            product = Product.objects.create(
                name=name,
                slug=f"{slug}-{random.randint(100, 999)}",
                description=f"{name} is a high quality product.",
                base_price=Decimal(random.randint(50, 1500)),
                vendor=random.choice(vendors),
                category=random.choice(categories),
                is_active=True,
            )
            products.append(product)

            for v in random.choice(variant_options):
                ProductVariant.objects.create(
                    product=product,
                    sku=f"{slug}-{v.lower().replace(' ', '-')}-{random.randint(1000, 9999)}",
                    variant_name=v,
                    price=product.base_price + Decimal(random.randint(10, 100)),
                    stock=random.randint(5, 50),
                )

            for i in range(3):
                label = f"{name} {i + 1}"
                try:
                    filename, content = self._fetch_placeholder(label)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Could not fetch image for {label}: {e}"))
                    continue

                img = ProductImage(
                    product=product,
                    alt_text=name,
                    is_primary=(i == 0),
                    display_order=i,
                )
                img.image_url.save(filename, content, save=True)

        self.stdout.write("Products, variants and images created.")

        for product in products:
            for user in random.sample(users, min(len(users), 3)):
                Review.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={
                        "rating": random.randint(3, 5),
                        "comment": random.choice([
                            "Great product!",
                            "Worth the price.",
                            "Good quality.",
                            "Highly recommended.",
                            "Satisfied with the purchase.",
                        ]),
                    },
                )

        self.stdout.write("Reviews created.")
        self.stdout.write(self.style.SUCCESS("Database population completed!"))