from __future__ import absolute_import, division, print_function
from flask import (Blueprint, g, redirect, render_template, request,
        url_for, session)
from sqlalchemy.exc import IntegrityError
import logging
from werkzeug import check_password_hash, generate_password_hash

from .. import db, sched
from ..utils import flash_errors, generate_verification_code
from .decorators import login_required, non_login_required
from .forms import FullRegisterForm, LoginForm
from .models import User
from ..phones.models import Phone
from ..phones.forms import PhoneVerificationForm

mod = Blueprint('users', __name__, url_prefix='/users')
logger = logging.getLogger('root')

#TODO This doesnt belong here. Basically just a stub for now to abstract
#this functionality of of views themselves.
def process_phone_verification(phone_number, verification_code):
    sched.send_message(
        'Welcome to AlarmAway! Your Verification code is %s'
        % verification_code,
        phone_number,
        )

@mod.route('/register', methods=['GET', 'POST'])
@non_login_required(alert='Already registered')
def register():
    """Main user registration page. Provides a full registration form.
    Upon succesful input validation, creates a new user.
    """

    form = FullRegisterForm(request.form)
    if form.validate_on_submit():
        # Form input is validated, but not checked against database yet.
        try:
            #hack while name isnt yet in all forms
            name = form.name.data
        except AttributeError:
            name = form.email.data.split('@')[0]

        new_user = User(
            name=name,
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            timezone = form.timezone.data,
            )
        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            form.email.errors.append(
                "Username/Email associated with an existing account",
                )
            flash_errors(form)
            return render_template('/users/register.html', form=form)

        new_phone = Phone(
            number=form.phone_number.data,
            owner=new_user
            )
        db.session.add(new_phone)
        try:
            db.session.commit()
        except IntegrityError:
            form.phone_number.errors.append(
                "Number already associated with an account."
                )
            #TODO this needs to be redirect(phones.add page or something
            # Although the phone add was unsucessful, the user was already
            # added to the database. This situation needs to be handled.
            session['user_id'] = new_user.id
            flash_errors(form)
            return redirect(url_for('phones.add'))

        verification_code = generate_verification_code()
        process_phone_verification(new_phone.number, verification_code)
        session['verification_code'] = verification_code
        session['user_id'] = new_user.id

        logger.debug(("""
            Successful user registration.
            User: {}
            Phone: {}
                """
            .format(new_user, new_phone)
            ))
        return redirect(url_for('users.home')) # END form.validate_on_submit
    flash_errors(form)
    return render_template('users/register.html', form=form)

@mod.route('/home')
@login_required
def home():
    user = g.user
    need_verify_phone, form = None, None
    for phone in user.phones:
        if not phone.verified:
            need_verify_phone = phone.id
            form = PhoneVerificationForm(request.form)
            break
    return render_template('users/home.html',
        user=user,
        verify_phone=need_verify_phone,
        form=form
        )

@mod.route('/account')
@login_required
def account():
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: users.account
        user_id: %s, method type: %s"""
        % (g.user.id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

@mod.route('/login', methods=['GET', 'POST'])
@non_login_required(alert='You are already logged in')
def login():
    """A basic user login page."""
    form = LoginForm(request.form)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            form.email.errors.append('Username/email does not exist')
        elif not check_password_hash(user.password, form.password.data):
            form.password.errors.append("Invalid password")
        else:
            session['user_id'] = user.id
            return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('users/login.html', form=form)

@mod.route('/logout')
def logout():
    """Standard Logout view. Clears the applications data from session and
    Logs the user out.
    """
    session.pop('verification_code', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))
