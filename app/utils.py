from __future__ import absolute_import, division, print_function
import random
from flask import flash

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
