from flask.ext.wtf import (Email, Form, PasswordField, Required, SelectField,
    TextField)
from app.forms import get_timezone_list, PhoneForm

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
