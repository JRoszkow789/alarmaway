from __future__ import absolute_import

from app.celery import celery
from app.phones.models import Phone
from app.users.models import User

from app.twilio_client import send_sms_message, send_phone_call

@celery.task
def send_verification(phone_id, verification_code):
    phone = Phone.query.filter_by(id=phone_id).first()
    message = """
        Welcome to AlarmAway!
        Complete registration by using the following code to verify your phone.
        Your verfication code is %s.
        """ % verification_code
    send_sms_message(phone.number, message)

def send_call(phone_id):
    phone = Phone.query.filter_by(id=phone_id).first()
    send_phone_call(phone.number)

@celery.task
def greet(name, id=None):
    """Basic task, tests both the message queue and it's db access.
    """
    if id is not None:
        user = User.query.filter_by(id=id).first()
        return "Hello %s, Is your email address %s?" % (name, user.email)
    return "Hello there %s, how are you today?" % name
