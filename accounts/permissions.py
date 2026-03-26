from rest_framework import permissions
from .models import User

class IsSelf(permissions.BasePermission):
    """Allow access only to the user themselves."""
    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.VENDOR


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.ADMIN