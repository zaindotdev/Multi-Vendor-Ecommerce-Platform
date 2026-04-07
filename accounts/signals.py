from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import User, CustomerProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CUSTOMER:
        CustomerProfile.objects.get_or_create(user=instance)