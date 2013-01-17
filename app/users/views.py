from __future__ import absolute_import
from flask import (Blueprint, redirect, render_template, request, url_for,
    session)
from sqlalchemy.exc import IntegrityError
import logging

from app import db
from app.utils import flash_errors, generate_verification_code
from app.users.forms import FullRegisterForm
from app.users.models import User
from app.phones.models import Phone

mod = Blueprint('users', __name__, url_prefix='/users')
logger = logging.getLogger('root')

@mod.route('/register', methods=['GET', 'POST'])
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
            password=form.password.data,
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
            session['user_id'] = new_user.id
            flash_errors(form)
            return redirect(url_for('phones.add_phone'))

        verification_code = generate_verification_code()
        #manager.process_verification(verification_code, Phone.number)
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
def home():
    return "User Home(Profile) Page"

@mod.route('/account')
def user_account():
    return "User account page"

@mod.route('/login', methods=['GET', 'POST'])
def login():
    return "User Login Page"

@mod.route('/logout')
def logout():
    return "User Logout Page"
