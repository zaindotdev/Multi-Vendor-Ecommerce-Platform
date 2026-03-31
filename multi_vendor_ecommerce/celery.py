from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multi_vendor_ecommerce.settings')
app = Celery('multi_vendor_ecommerce')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
