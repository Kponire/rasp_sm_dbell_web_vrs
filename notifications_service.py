import os
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv

load_dotenv()


SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM')  # e.g. 'whatsapp:+1415xxxxxxx'


def send_email(to_email: str, subject: str, html_content: str, from_email: str = None) -> dict:
    if not SENDGRID_API_KEY:
        raise RuntimeError('SENDGRID_API_KEY must be set')
    from_email = from_email or os.getenv('DEFAULT_FROM_EMAIL') or 'no-reply@example.com'
    message = Mail(from_email=from_email, to_emails=to_email, subject=subject, html_content=html_content)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    resp = sg.send(message)
    return {'status_code': resp.status_code, 'body': getattr(resp, 'body', None)}


def send_whatsapp(to_number: str, message_body: str) -> dict:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM):
        raise RuntimeError('Twilio credentials and TWILIO_WHATSAPP_FROM must be set')
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(body=message_body, from_=TWILIO_WHATSAPP_FROM, to=f'whatsapp:{to_number}')
    return {'sid': msg.sid, 'status': msg.status}
