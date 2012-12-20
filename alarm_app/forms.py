from flask.ext.wtf import BooleanField, Email, Form, PasswordField, Required
from flask.ext.wtf import SelectField, TextField
import pytz

def get_timezone_list():
    return pytz.country_timezones('US')

class LoginForm(Form):
    email = TextField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])

class RegisterForm(Form):
    email = TextField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])
    timezone = SelectField('Timezone', [Required()],
        choices=get_timezone_list())
    accept_tos = BooleanField('I accept the TOS', [Required()])
