from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.db.models.signals import post_save
from django.dispatch import receiver


class TimeStampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CustomUserManager(UserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser, TimeStampMixin):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        VENDOR = 'vendor', 'Vendor'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class Address(TimeStampMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'addresses'

    def save(self, *args, **kwargs):
        # Enforce only one default address per user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address_line_1}, {self.city}, {self.country}"


class VendorProfile(TimeStampMixin):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=255)
    company_description = models.TextField(blank=True)
    company_slug = models.SlugField(unique=True)
    logo_url = models.URLField(blank=True)
    banner_url = models.URLField(blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    payout_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_approved = models.BooleanField(default=False)
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.company_name


class CustomerProfile(TimeStampMixin):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.username

    @property
    def default_address(self):
        return self.user.addresses.filter(is_default=True).first()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.VENDOR:
        VendorProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.CUSTOMER:
        CustomerProfile.objects.get_or_create(user=instance)