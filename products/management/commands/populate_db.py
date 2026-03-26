from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random

from products.models import Category, Product, ProductVariant, ProductImage, Review

User = get_user_model()


class Command(BaseCommand):
    help = "Populate database with sample products"

    def handle(self, *args, **kwargs):

        self.stdout.write("Starting database population...")

        users = list(User.objects.all())

        if not users:
            self.stdout.write(self.style.ERROR("No users found. Create users first."))
            return

        vendors = users[:3] if len(users) >= 3 else users

        # ----------------
        # Categories
        # ----------------
        electronics, _ = Category.objects.get_or_create(
            name="Electronics", slug="electronics"
        )

        phones, _ = Category.objects.get_or_create(
            name="Phones", slug="phones", parent=electronics
        )

        laptops, _ = Category.objects.get_or_create(
            name="Laptops", slug="laptops", parent=electronics
        )

        fashion, _ = Category.objects.get_or_create(
            name="Fashion", slug="fashion"
        )

        shoes, _ = Category.objects.get_or_create(
            name="Shoes", slug="shoes", parent=fashion
        )

        categories = [phones, laptops, shoes]

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
                slug=f"{slug}-{random.randint(100,999)}",
                description=f"{name} is a high quality product.",
                base_price=Decimal(random.randint(50, 1500)),
                vendor=random.choice(vendors),
                category=random.choice(categories),
                is_active=True,
            )

            products.append(product)

            variants = random.choice(variant_options)

            for v in variants:
                ProductVariant.objects.create(
                    product=product,
                    sku=f"{slug}-{v.lower().replace(' ','-')}-{random.randint(1000,9999)}",
                    variant_name=v,
                    price=product.base_price + Decimal(random.randint(10, 100)),
                    stock=random.randint(5, 50),
                )

            for i in range(3):
                ProductImage.objects.create(
                    product=product,
                    image_url=f"https://placehold.co/600x400?text={name.replace(' ','+')}",
                    alt_text=name,
                    is_primary=(i == 0),
                    display_order=i,
                )

        self.stdout.write("Products, variants and images created.")

        for product in products:
            review_users = random.sample(users, min(len(users), 3))

            for user in review_users:
                Review.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={
                        "rating": random.randint(3, 5),
                        "comment": random.choice(
                            [
                                "Great product!",
                                "Worth the price.",
                                "Good quality.",
                                "Highly recommended.",
                                "Satisfied with the purchase.",
                            ]
                        ),
                    },
                )

        self.stdout.write("Reviews created.")
        self.stdout.write(self.style.SUCCESS("Database population completed!"))