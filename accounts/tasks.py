from celery import shared_task
from utils.send_mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_verification_email(self, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        token = signing.dumps({'user_id': user.id})
        verify_url = settings.FRONTEND_URL + "verify" + f'?token={token}'
        send_mail(
            to=user.email,
            subject='Verify Your Email',
            message=f'Please verify your email by clicking the following link: {verify_url}',
            html=f'<p>Please verify your email by clicking <a href="{verify_url}">this link</a>.</p>',
        )
    except Exception as exc:
        logger.exception('send_verification_email failed for user %s.', user_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_vendor_approval_mail_to_admin(self, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        admins = User.objects.filter(role=User.Role.ADMIN)
        if not admins.exists():
            logger.warning('send_vendor_approval_mail_to_admin: No admin users found.')
            return
        for admin in admins:
            send_mail(
                to=admin.email,
                subject='New Vendor Registration — Approval Required',
                message=f'User {user.username} ({user.email}) has registered as a vendor and is awaiting approval.',
                html=f'<p><strong>{user.username}</strong> ({user.email}) has registered as a vendor and is awaiting your approval.</p>',
            )
    except Exception as exc:
        logger.exception('send_vendor_approval_mail_to_admin failed for user %s.', user_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)