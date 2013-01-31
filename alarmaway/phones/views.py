from __future__ import absolute_import, division, print_function
import logging
from flask import (
    Blueprint, flash, g, redirect, request, render_template, session, url_for
    )
from sqlalchemy.exc import IntegrityError

from .. import db, task_manager
from ..utils import flash_errors, generate_verification_code
from .forms import PhoneForm, PhoneVerificationForm
from .models import Phone
from ..users.decorators import login_required

mod = Blueprint('phones', __name__, url_prefix='/phones')
logger = logging.getLogger("alarmaway")

@mod.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Standard view for adding a new phone. Requires a current logged in user,
    with no currently unverified phones. If these requirements are met and
    input is valid, the new phone is added to database and verification is
    proceessed.
    """

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
            form.phone_number.errors.append("Number is already registered.")
        except:
            logger.error("Unknown exception caught in add_phone.\n%s" % err)
            flash("Oops, something went wrong... Please try again.")
        else:
            logger.info("New phone added {}".format(new_phone))
            verification_code = generate_verification_code()
            task_manager.processPhoneVerification(new_phone, verification_code)
            session['verification_code'] = verification_code
            flash('New phone number added!', 'success',)
            return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('phones/add.html', form=form)

@mod.route('/verify/<phone_id>', methods=['GET', 'POST'])
@login_required
def verify(phone_id):
    """Standard View for verifying user's phones. Requires a verification code
    to exist in the current session, and a logged in user. If these conditions
    are met and the user's entered code is correct, verify the phone in db and
    alert the user of status.
    """

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
            logger.info(
                "Invalid verification attempt - user: {}, "
                "attempt: {}, correct: {}".format(
                    g.user,
                    form.verification_code.data,
                    session['verification_code'],
            ))
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
                logger.info("phone verified {}".format(phone))
                flash('Phone successfully verified!', 'success')
                return redirect(url_for('users.home'))
    flash_errors(form)
    return render_template('phones/verify.html', form=form, phone=phone)

@mod.route('/remove/<phone_id>')
@login_required
def remove(phone_id):
    """Standard view for removing a phone number from the system. Requires
    a logged in user who owns the requested phone to call this method,
    then attempts to delete the phone from db and alerts user of status.
    """

    phone = Phone.query.filter_by(id=phone_id, owner=g.user).first()
    if not phone:
        flash("Phone not found or ownership not verified.", 'error')
        return redirect(url_for('users.home'))
    p_id = phone.id # For logging
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
        logger.info("Phone removed {}".format(p_id))
        flash('Phone successfully removed!', 'success')
    return redirect(url_for('users.home'))
