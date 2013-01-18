from __future__ import absolute_import, unicode_literals
import logging
from flask import (
    Blueprint, flash, g, redirect, request, render_template, url_for
    )
from app import db
from app.forms import RegisterBeginForm
from app.phones.forms import AddPhoneForm
from app.phones.models import Phone
from ..users.decorators import login_required

mod = Blueprint('phones', __name__, url_prefix='/phones')
logger = logging.getLogger('root')

@mod.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: phones.add
        user_id: %s, method type: %s"""
        % (g.user.id, request.method)
        )
    logger.debug(info_msg)
    return info_msg
    #if Phone.query.filter_by(id=user['user_id'], verified=False).first():
    #    # User already has an unverified phone, alert and redirect them.
    #    flash("Error: You already have an unverified phone. Verify first.")
    #    return redirect(url_for('user_home'))

    #form = RegisterBeginForm(request.form)
    #if form.validate_on_submit():
    #    return "Number validated: %s" % form.phone_number.data
        # Form validation checks for correct format and presence, but we
        # still need to check that the number doesn't already exist in db.
        #try:
        #    new_phone = Phone(form.phone_number.data, owner=user, verified=False)
        #except IntegrityError, err:
        #    logger.info(
        #        "IntegrityError raised in phones.add_phone\nmsg: %s" % err
        #        )
        #    flash("Error: That phone already belongs to someone.")
        #    return redirect(url_for('user_home'))
        #except:
        #    logger.warn(
        #        "Unknown error threw exception in add_phone.\nmsg: %s" % err
        #        )
        #    flash("An unknown error has occured. Please try again.")
        #    return redirect(url_for('user_home'))
        #else:
        #    return "Success!"
        #user_code = generate_verification_code()
        #send_phone_verification()
    #return render_template('phones/add.html', form=form)


@mod.route('/verify/<phone_id>', methods=['GET', 'POST'])
def verify(phone_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: phones.verify
        phone_id: %s, method type: %s"""
        % (phone_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

@mod.route('/remove/<phone_id>', methods=['GET', 'POST'])
def remove(phone_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: phones.remove
        phone_id: %s, method type: %s"""
        % (phone_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg
