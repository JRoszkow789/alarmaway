from __future__ import absolute_import, division, print_function
from flask import (Blueprint, g, redirect, render_template, request,
        url_for, session)
from sqlalchemy.exc import IntegrityError
import logging
from werkzeug import check_password_hash, generate_password_hash

from .. import db, task_manager
from ..utils import flash_errors, generate_verification_code
from .decorators import login_required, non_login_required
from .forms import LoginForm, MainRegisterForm
from .models import User
from ..phones.models import Phone
from ..phones.forms import PhoneForm, PhoneVerificationForm

mod = Blueprint('users', __name__, url_prefix='/users')
logger = logging.getLogger("alarmaway")

@mod.route('/register', methods=['GET', 'POST'])
@non_login_required(alert='Already registered')
def register():
    """Main user registration page. Provides a full registration form.
    Upon succesful input validation, creates a new user.
    """

    form = MainRegisterForm(request.form)
    if form.validate_on_submit():
        new_user = User(
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
        else:
            logger.info("New user created: {}".format(new_user))
            task_manager.processWelcomeEmail(new_user)

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
            # Although the phone add was unsucessful, the user was already
            # added to the database. This situation needs to be handled.
            session['user_id'] = new_user.id
            flash_errors(form)
            return redirect(url_for('phones.add'))
        else:
            logger.info("New phone created: {}".format(new_phone))
            verification_code = generate_verification_code()
            task_manager.processPhoneVerification(new_phone, verification_code)
            session['verification_code'] = verification_code

        session['user_id'] = new_user.id
        return redirect(url_for('users.home')) # END form.validate_on_submit

    flash_errors(form)
    signin_form = LoginForm(request.form)
    return render_template('users/register.html', form=form, signin_form=signin_form)

@mod.route('/try', methods=['GET', 'POST'])
def trial():
    """A view to handle the registration form on the home page."""
    form = MainRegisterForm(request.form)
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            name=form.name.data,
            timezone=form.timezone.data,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            form.email.errors.append(
                "Username/Email associated with an existing account",
                )
        else:
            task_manager.processWelcomeEmail(user)
            logger.info("New user registered: {}".format(user))
            session['user_id'] = user.id
            session['firstphone'] = True
            return redirect(url_for('phones.add'))
    flash_errors(form)
    signin_form = LoginForm()
    #This ruins the whole blueprint idea and needs to be fixed
    return render_template('frontend/index.html', form=form, signin_form=signin_form)


@mod.route('/home')
@login_required
def home():
    """Main user home page. This is where user's are typically redirected to
    after successful actions in the system, also where they come right after
    signing up or logging in. Displays basic user, phone, and alarm data.
    """

    user = g.user
    need_verify_phone, form = None, None
    alarms = user.alarms.all()
    phones = user.phones.all()
    if not phones:
        form = PhoneForm(request.form)
    else:
        for phone in phones:
            if not phone.verified:
                need_verify_phone = phone.id
                form = PhoneVerificationForm(request.form)
                break
    return render_template('users/home.html',
        user=user,
        verify_phone=need_verify_phone,
        form=form,
        alarms=alarms,
        phones=phones,
        )

@mod.route('/account')
@login_required
def account():
    """Represents an 'account' page for the user. This page will hold more
    administrative information compared to the typical user home page. I.E
    billing, account status, change password, etc...
    """
    logger.info("View users.account called")
    return redirect(url_for('users.home'))

@mod.route('/login', methods=['GET', 'POST'])
@non_login_required(alert='You are already logged in')
def login():
    """A basic user login page."""

    form = LoginForm(request.form)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            form.email.errors.append('No account found with that email address')
        elif not check_password_hash(user.password, form.password.data):
            form.password.errors.append("Invalid password")
            logger.info("Invalid password attempt for user {}".format(user))
        else:
            session['user_id'] = user.id
            logger.info("Successful user login: {}".format(user.id))
            return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('users/login.html', signin_form=form, form=form)

@mod.route('/logout')
def logout():
    """Standard Logout view. Clears the applications data from session and
    Logs the user out.
    """

    logger.info("Logout popping verification_code {}".format(
        session.pop('verification_code', "None")))
    logger.info("Logout popping user_id {}".format(
        session.pop('user_id', "None")))
    return redirect(url_for('frontend.home'))
