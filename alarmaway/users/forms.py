from flask.ext.wtf import (Email, Form, PasswordField, Required, SelectField,
    TextField)
from flask.ext.wtf.html5 import EmailField
from ..utils import get_timezone_list
from ..phones.forms import PhoneForm

class MainRegisterForm(Form):
    """A form that includes just the main info necessary for registration:
    username(optional), email, password, timezone.
    """

    name = TextField('Username (optional)',)
    email = TextField('Email address', [Required(), Email()])
    password = PasswordField('Password', [Required(),])
    timezone = SelectField('Timezone', [Required(),],
        choices=([(None, 'Choose your timezone...'),]
            + [(timezone, timezone) for timezone in get_timezone_list()]))

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
    email = EmailField('Email Address', [Required(), Email()])
    password = PasswordField('Password', [Required()])
