import re
from flask.ext.wtf import Form, Required, TextField
from flask.ext.wtf.html5 import TelField

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

class PhoneVerificationForm(Form):
    """A basic verification form to take in the user's verification code
    attempt.
    """
    verification_code = TextField('Verification code', [Required(),])
