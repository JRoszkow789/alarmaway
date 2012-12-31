import pytz

from flask.ext.wtf import Form, SelectField, Required, Email, PasswordField
from flask.ext.wtf.html5 import TelField

def get_timezone_list():
    """Returns a list of US timezones as indicated in the pytz module.
    """
    return pytz.country_timezones('US')

class RegisterBeginForm(Form):
    """A small form to begin user registration. Developed for the alarmaway
    homepage, it contains just two fields:

    phone_number :: an html5 'tel' field widget, also represented as a
                    TextField for older browsers, captures the user's phone
                    number.
    timezone     :: a single-item select field containing all the available
                    timezones from which a user may choose. Timeszones are
                    populated from the get_timezone_list function.
    """
    phone_number = TelField('Phone Number', [Required()])
    timezone = SelectField('Timezone', [Required(),],
        choices=([(None, 'Choose your timezone...'),]
            + [(timezone, timezone) for timezone in get_timezone_list()]))
