from functools import wraps
from flask import g, flash, request, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('You must be logged in to view that page', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def non_login_required(alert='', severity='info'):
    def func_wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is not None:
                if alert:
                    flash(alert, severity)
                return redirect(url_for('user_home'))
            return f(*args, **kwargs)
        return decorated_function
    return func_wrapper
