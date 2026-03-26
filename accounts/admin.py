from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address, VendorProfile, CustomerProfile


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ('address_line_1', 'address_line_2', 'city', 'state', 'postal_code', 'country', 'is_default')
    readonly_fields = ('is_default',)


class VendorProfileInline(admin.StackedInline):
    model = VendorProfile
    extra = 0
    can_delete = False
    fields = ('company_name', 'company_slug', 'company_description', 'logo_url', 'banner_url', 'commission_rate', 'payout_threshold', 'is_approved')


class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    extra = 0
    can_delete = False
    fields = ('phone_number',)


def get_inlines(obj):
    """Return the correct inlines based on the user's role."""
    if obj is None:
        return []
    inlines = [AddressInline]
    if obj.role == User.Role.VENDOR:
        inlines.append(VendorProfileInline)
    elif obj.role == User.Role.CUSTOMER:
        inlines.append(CustomerProfileInline)
    return inlines



@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')

    # Extend BaseUserAdmin fieldsets with our custom fields
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Timestamps', {
            'fields': ('role', 'created_at', 'updated_at')
        }),
    )

    def get_inlines(self, request, obj=None):
        return get_inlines(obj)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_line_1', 'city', 'country', 'is_default')
    list_filter = ('country', 'is_default')
    search_fields = ('user__username', 'address_line_1', 'city', 'country')


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'commission_rate', 'payout_threshold', 'is_approved')
    list_filter = ('is_approved',)
    search_fields = ('user__username', 'company_name', 'company_slug')
    actions = ['approve_vendors']

    @admin.action(description='Approve selected vendors')
    def approve_vendors(self, request, queryset):
        queryset.update(is_approved=True)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'phone_number')