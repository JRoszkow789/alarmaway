from functools import wraps
from flask import g, flash, request, redirect, url_for

from .. import app

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('You must be logged in to view that page', 'error')
            return redirect(url_for('users.login', next=request.url))
        elif g.user.email.lower() not in app.config['SUPER_USERS']:
            flash('You do not have the proper credentials.', 'error')
            return redirect(url_for('users.home'))
        return f(*args, **kwargs)
    return decorated_function
