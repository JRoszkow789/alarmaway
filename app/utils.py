from __future__ import absolute_import, division, print_function
from datetime import datetime
import random
from flask import flash
import pytz

def flash_errors(form):
    """Helper method to render all of the errors in the given form
    as flask flash_messages for formatted display.
    """
    for field, errors in form.errors.items():
        for error in errors:
            field_name = getattr(form, field).label.text
            error_message = "Error in the %s field - %s" % (field_name, error)
            flash(error_message, 'error')

def generate_verification_code():
    """Generates a new (pseudo)random 7 digit number string used primarily
    for passing to user and verifying new phone numbers.
    """
    new_ver_code = str(random.randint(1000000, 9999999))
    return new_ver_code

def get_utc(local_tm, tz):
    """Takes a datetime.time() object and a string representing a timezone,
       and uses this information and the pytz library to convert time to UTC.
    """
    utc_tz = pytz.utc
    utc_now = datetime.utcnow().replace(tzinfo=utc_tz)
    local_tz = pytz.timezone(tz)
    local_now = local_tz.normalize(utc_now)
    local_alarm = local_now.replace(hour=local_tm.hour, minute=local_tm.minute)
    utc_alarm = utc_tz.normalize(local_alarm)
    return utc_alarm.time()

def get_local(utc_time, tz):
    """Takes a datetime.time() object and a string representing a timezone,
       and uses this information and the pytz library to convert this UTC
       time to a local time in the given timezone.
    """
    utc_tz = pytz.utc
    utc_now = datetime.utcnow().replace(tzinfo=utc_tz)
    utc_alarm = utc_now.replace(hour=utc_time.hour, minute=utc_time.minute)
    local_tz = pytz.timezone(tz)
    local_alarm = local_tz.normalize(utc_alarm)
    return local_alarm.time()
