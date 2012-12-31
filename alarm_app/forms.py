from flask.ext.wtf import Email, Form, PasswordField, Required
from flask.ext.wtf import SelectField, TextField
from flask.ext.wtf.html5 import TelField
import pytz

def get_timezone_list():
    tz_list = [(tz, tz) for tz in pytz.country_timezones('US')]
    return [(None, 'Choose timezone...'),] + tz_list

class LoginForm(Form):
    email = TextField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])

class RegisterForm(Form):
    email = TextField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])
    timezone = SelectField('Timezone', [Required()],
        choices=get_timezone_list())

class NewPhoneForm(Form):
    phone_number = TelField('Phone Number', [Required()])
