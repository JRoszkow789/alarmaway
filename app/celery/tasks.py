from __future__ import absolute_import

import logging
from twilio.rest import TwilioRestClient

from .celery import celery
from .config import (
    TWILIO_FROM_NUMBER, TWILIO_ACCOUNT_ID, TWILIO_SECRET_TOKEN,
    DEFAULT_CALL_URL
)
from ..phones.models import Phone
from ..users.models import User


logger = logging.getLogger(__name__)

client = TwilioRestClient(
    account=TWILIO_ACCOUNT_ID,
    token=TWILIO_SECRET_TOKEN,
    )

@celery.task
def send_sms_message(phone_id, message, *args, **kwargs):
    phone = Phone.query.filter_by(id=phone_id).first()
    sms_message = client.sms.messages.create(
        to=phone.number,
        from_=TWILIO_FROM_NUMBER,
        body=message,
        )
    logger.info("sms_message sent: %s" % sms_message)

@celery.task
def send_phone_call(phone_id, message_url=DEFAULT_CALL_URL):
    phone = Phone.query.filter_by(id=phone_id).first()
    phone_call = client.calls.create(
        to=phone.number,
        from_=TWILIO_FROM_NUMBER,
        url=message_url,
        )
    logger.info("phone call sent: %s" % phone_call)

@celery.task
def greet(name, id=None):
    """Basic task, tests both the message queue and it's db access.
    """
    if id is not None:
        user = User.query.filter_by(id=id).first()
        return "Hello %s, Is your email address %s?" % (name, user.email)
    return "Hello there %s, how are you today?" % name
