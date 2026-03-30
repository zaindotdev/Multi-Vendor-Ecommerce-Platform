from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Product


class IsVendor(BasePermission):
    message = "Only vendors can create products."

    def has_permission(self, request, view) -> bool:
        if request.method != "POST":
            return True
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "vendor")


class IsProductOwner(BasePermission):

    message = "Only the product owner can modify this resource."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True

        if not (request.user and request.user.is_authenticated):
            return False

        if view.basename == "product" and request.method == "POST":
            return IsVendor().has_permission(request, view)

        if view.basename in {"product-variant", "product-image"} and request.method == "POST":
            product_id = request.data.get("product")
            if not product_id:
                return False
            try:
                product = Product.objects.only("vendor_id").get(pk=product_id)
            except Product.DoesNotExist:
                return False
            return product.vendor_id == request.user.id

        return True

    def has_object_permission(self, request, view, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        if not (request.user and request.user.is_authenticated):
            return False

        if isinstance(obj, Product):
            return obj.vendor_id == request.user.id

        product = getattr(obj, "product", None)
        if product is None:
            return False

        return product.vendor_id == request.user.id
