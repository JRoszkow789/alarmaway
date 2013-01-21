import re

from flask.ext.wtf import Form, SelectField, Required, Email, PasswordField
from flask.ext.wtf import TextField
from flask.ext.wtf.html5 import TelField

import pytz

PHONE_RE = re.compile(
    r"^\(?([0-9]{3})\)?[. -]?([0-9]{3})[. -]?([0-9]{4})$")


def validate_number(num):
    """Validates a phone number to ensure it is in a valid format and returns
       the phone number in the correct format for our application.
    """
    rv = PHONE_RE.search(num)
    try:
        return rv.group(1) + rv.group(2) + rv.group(3)
    except AttributeError:
        return False

class PhoneForm(Form):
    phone_number = TelField('Phone number', [Required(),])

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        formatted_number = validate_number(self.phone_number.data)
        if not formatted_number:
            self.phone_number.errors.append('Not a valid phone number')
            return False

        self.phone_number.data = formatted_number
        return True

def get_timezone_list():
    """Returns a list of US timezones as indicated in the pytz module.
    """
    return pytz.country_timezones('US')


def populate_alarm_times():
    """
    """
    alarm_times = [(None, 'Choose a time'),]
    for hour in range(0, 24):
        for minute in range(0, 60, 10):
            alarm_times.append((
                '%.2d:%.2d' % (hour, minute),
                '%d:%.2d %.2s' % ((hour if hour <= 12 else hour - 12),
                minute, ('AM' if hour < 12 else 'PM'))))
    return alarm_times


class AddUserAlarmForm(Form):
    """
    """
    alarm_time = SelectField('Alarm time', [Required()],
        choices=populate_alarm_times())
    phone_number = SelectField('Phone number', [Required()], coerce=int)

    def __repr__(self):
        return '<AddUserAlarmForm - phones: %s>' % self.phone_number.choices


class RegisterBeginForm(PhoneForm):
    """A small form to begin user registration. Developed for the alarmaway
    homepage, it contains just two fields:

    phone_number :: an html5 'tel' field widget, also represented as a
                    TextField for older browsers, captures the user's phone
                    number.
    timezone     :: a single-item select field containing all the available
                    timezones from which a user may choose. Timeszones are
                    populated from the get_timezone_list function.
    """
    #phone_number = TelField('Phone Number', [Required()])
    timezone = SelectField('Timezone', [Required(),],
        choices=([(None, 'Choose your timezone...'),]
            + [(timezone, timezone) for timezone in get_timezone_list()]))


class RegisterContinueForm(Form):
    """
    """
    email = TextField('Your email address', [Required(), Email()])
    password = PasswordField('Create a password', [Required()])


class FullRegisterForm(PhoneForm):
    """
    """
    email = TextField('Email address', [Required(), Email()])
    password = PasswordField('Password', [Required(),])
    timezone = SelectField('Timezone', [Required(),],
        choices=([(None, 'Choose your timezone...'),]
            + [(timezone, timezone) for timezone in get_timezone_list()]))


class LoginForm(Form):
    """A basic login form. Includes an email field and a password field.
    """
    email = TextField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])

    def __repr__(self):
        return "<LoginForm(flask.WTF) :: Fields %s>" % (locals)

class PhoneVerificationForm(Form):
    """A basic verification form to take in the user's verification code
    attempt.
    """
    verification_code = TextField('Verification code', [Required(),])
