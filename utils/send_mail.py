import os
import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY

def send_mail(to, subject, message, html=None):
    params: resend.Emails.SendParams = {
        "from": "Multi Vendor Ecommerce <no-reply@interview-ai.live>",
        "to": [to],
        "subject": subject,
        'text': message,
        "html": html,
    }
    try:
        email = resend.Emails.send(params)
        print(email)
    except Exception as e:
        print(f"Error sending email: {e}")