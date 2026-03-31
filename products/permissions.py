from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Product


class IsAdminUser(BasePermission):
    message = 'Only admins can perform this action.'

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'admin'
        )


class IsVendor(BasePermission):
    message = 'Only vendors can perform this action.'

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'vendor'
        )


class IsProductOwner(BasePermission):
    message = 'Only the product owner can modify this resource.'

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True

        if not (request.user and request.user.is_authenticated):
            return False

        if view.basename == 'product' and request.method == 'POST':
            return getattr(request.user, 'role', None) == 'vendor'

        if view.basename in {'product-variant', 'product-image'} and request.method == 'POST':
            product_id = request.data.get('product')
            if not product_id:
                return False
            try:
                product = Product.objects.only('vendor_id').get(pk=product_id)
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

        product = getattr(obj, 'product', None)
        if product is None:
            return False

        return product.vendor_id == request.user.id