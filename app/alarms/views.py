from __future__ import absolute_import, division, print_function
import logging
from flask import (Blueprint, flash, g, redirect, render_template,
    request, url_for
)
from .. import db
from ..utils import get_utc
from ..phones.models import Phone
from .forms import AddUserAlarmForm
from .models import Alarm

mod = Blueprint('alarms', __name__, url_prefix='/alarms')
logger = logging.getLogger(__name__)

@mod.route('/add', methods=['GET', 'POST'])
def add():
    """Provides a form and view to assist a user in adding a new alarm.
    If POST-ed to, attempts to validate the form's data and user in session
    and add the alarm to the database.
    """

    user = g.user
    form = AddUserAlarmForm(request.form)
    form.phone_number.choices = [
        (phone.id, phone.number)
        for phone in user.phones
    ]
    if form.validate_on_submit():
        #TODO This assumes that the previous code's function is handled in form
        #time = datetime.strptime(form.time.data, '%H:%M')
        utc_alarm_time = get_utc(form.alarm_time.data, user.timezone)
        alarm_phone = Phone.query.filter_by(
            id=form.phone_number.data,
            owner=user,
        ).first()
        alarm = Alarm(
            time=utc_alarm_time,
            owner=user,
            phone=alarm_phone
        )
        db.session.add(alarm)
        try:
            db.session.commit()
        except:
            #TODO Add correct exception handling
            flash("Could not add alarm, please try again.", 'error')
            return redirect(url_for('users.home'))
        logger.debug('New alarm created, needs to be set.\n%s' % alarm)
        flash('Your alarm has been created', 'success')
        return redirect(url_for('users.home'))
    return render_template('alarms/add.html', form=form)

@mod.route('/remove/<alarm_id>', methods=['GET', 'POST'])
def remove(alarm_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: alarms.remove
        alarm_id: %s, method type: %s"""
        % (alarm_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

@mod.route('/update/<alarm_id>', methods=['GET', 'POST'])
def update(alarm_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: alarms.update
        alarm_id: %s, method type: %s"""
        % (alarm_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

@mod.route('/set/<alarm_id>', methods=['GET', 'POST'])
def set(alarm_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: alarms.set
        alarm id: %s, method type: %s"""
        % (alarm_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

@mod.route('/unset/<alarm_id>', methods=['GET', 'POST'])
def unset(alarm_id):
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: alarms.unset
        alarm id: %s, method type: %s"""
        % (alarm_id, request.method)
        )
    logger.debug(info_msg)
    return info_msg
