from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse

@shared_task(bind=True, max_retries=3)
def send_verification_email(self, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        token = signing.dumps({'user_id': user.id})
        verify_url = settings.FRONTEND_URL + reverse('accounts:verify-email') + f'?token={token}'
        send_mail(
            'Verify your email',
            f'Click the link to verify your email: {verify_url}',
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
