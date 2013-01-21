from __future__ import absolute_import, division, print_function
import logging
from flask import (
    Blueprint, flash, g, redirect, request, render_template, session, url_for
    )
from sqlalchemy.exc import IntegrityError

from .. import db, sched
from ..utils import flash_errors, generate_verification_code
from .forms import PhoneForm, PhoneVerificationForm
from .models import Phone
from ..users.decorators import login_required

mod = Blueprint('phones', __name__, url_prefix='/phones')
logger = logging.getLogger('root')

#TODO This doesnt belong here. Basically just a stub for now to abstract
#this functionality of of views themselves.
def process_phone_verification(phone_number, verification_code):
    sched.send_message(
        'Welcome to AlarmAway! Your Verification code is %s'
        % verification_code,
        phone_number,
    )

@mod.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    user = g.user
    if Phone.query.filter_by(owner=user, verified=False).first():
        # User already has an unverified phone, alert and redirect them.
        flash("You already have an unverified phone. Verify first.", 'error')
        return redirect(url_for('users.home'))

    form = PhoneForm(request.form)
    if form.validate_on_submit():
        # Form validation checks for correct format and presence, but we
        # still need to check that the number doesn't already exist in db.
        new_phone = Phone(form.phone_number.data, owner=user, verified=False)
        db.session.add(new_phone)
        try:
            db.session.commit()
        except IntegrityError, err:
            logger.debug("Error adding new phone.\n%s" % err)
            form.phone_number.errors.append("Number is already registered.")
        except:
            logger.error("Unknown exception caught in add_phone.\n%s" % err)
            flash("Oops, something went wrong... Please try again.")
        else:
            verification_code = generate_verification_code()
            process_phone_verification(new_phone.number, verification_code)
            session['verification_code'] = verification_code
            flash('New phone number added!', 'success',)
            return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('phones/add.html', form=form)

@mod.route('/verify/<phone_id>', methods=['GET', 'POST'])
@login_required
def verify(phone_id):
    if 'verification_code' not in session:
        logger.info('attempted to verify phone with no code in session')
        flash('No verification code found. Please request a new one.', 'error')
        return redirect(url_for('users.home'))
    phone = Phone.query.filter_by(id=phone_id, owner=g.user).first()
    if not phone:
        flash('Phone not found or ownership not verified', 'error')
        return redirect(url_for('users.home'))
    form = PhoneVerificationForm(request.form)
    if form.validate_on_submit():
        if form.verification_code.data != session['verification_code']:
            form.verification_code.errors.append('Invalid verification code')
        else:
            phone.verified = True
            db.session.add(phone)
            try:
                db.session.commit()
            except:
                logger.warn("""
                    Error updating phone status to verified
                    phone id: %s, user id: %s""" % phone_id, g.user.id
                )
                flash('Oops, Something went wrong... Please try again', 'error')
            else:
                flash('Phone successfully verified!', 'success')
                return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('phones/verify.html', form=form, phone=phone)

@mod.route('/remove/<phone_id>')
@login_required
def remove(phone_id):
    phone = Phone.query.filter_by(id=phone_id, owner=g.user).first()
    if not phone:
        flash("Phone not found or ownership not verified.", 'error')
        return redirect(url_for('users.home'))
    db.session.delete(phone)
    try:
        db.session.commit()
    except Exception, err:
        logger.error("""
            Couldnt commit phone deletion.
            Phone id: %s, user id: %s
            user's phones: %s
            message: %s
            """ % (phone.id, g.user.id, g.user.phones, err)
        )
        flash(
            "Oops, something didnt work right, please try again.",
            'error',
        )
    else:
        flash('Phone successfully removed!', 'success')
    return redirect(url_for('users.home'))
