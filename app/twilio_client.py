from __future__ import absolute_import
from twilio.rest import TwilioRestClient

TWILIO_ACCOUNT_ID = 'AC52113fd0906659e7c6091e1c5d754ac7'
TWILIO_SECRET_TOKEN = '799a5ee66e106ca62f1f2fff8ba24220'
TWILIO_FROM_NUMBER = '8133584864'
DEFAULT_CALL_URL = 'http://canopyinnovation.com/twresp.xml'


client = TwilioRestClient(
    account=TWILIO_ACCOUNT_ID,
    token=TWILIO_SECRET_TOKEN,
)

from_number = TWILIO_FROM_NUMBER

def send_sms_message(to_number, message):
    sms_message = client.sms.messages.create(
        to=to_number,
        from_=from_number,
        body=message,
    )

def send_phone_call(to_number, message_url=DEFAULT_CALL_URL):
    phone_call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=message_url,
    )
