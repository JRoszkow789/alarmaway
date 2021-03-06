from __future__ import absolute_import, division, print_function
from flask import (Blueprint, flash, g, redirect, render_template,
    request, session, url_for
)

from .. import db, task_manager, format_phone_number
from ..utils import get_utc
from ..phones.models import Phone
from ..users.decorators import login_required
from .forms import AddUserAlarmForm
from .models import Alarm

mod = Blueprint('alarms', __name__, url_prefix='/alarms')
import logging
logger = logging.getLogger('alarmaway')

@mod.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Provides a form and view to assist a user in adding a new alarm.
    If POST-ed to, attempts to validate the form's data and user in session
    and add the alarm to the database.
    """

    user = g.user
    form = AddUserAlarmForm(request.form)
    form.phone_number.choices = [
        (phone.id, format_phone_number(phone.number))
        for phone in user.phones
    ]
    if form.validate_on_submit():
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
        else:
            logger.info("New alarm created {}".format(alarm))
            task_manager.processSetAlarm(alarm)
            flash('Your alarm has been created and set', 'success')
            session.pop('firstalarm', None)
        return redirect(url_for('users.home'))

    if session.get('firstalarm', False):
        template_name = 'firstalarm'
    else:
        template_name = 'add'

    return render_template('alarms/'+template_name+'.html', form=form)

@mod.route('/remove/<alarm_id>')
@login_required
def remove(alarm_id):
    alarm = (Alarm.query
        .filter_by(id=alarm_id, owner=g.user)
        .first_or_404()
        )
    if alarm.active:
        flash(
            "That alarm is still active! Unset it first, then try again.",
            'error',
        )
    else:
        task_manager.processRemoveAlarm(alarm)
        flash("Alarm removed!", 'success')
    return redirect(url_for('users.home'))

@mod.route('/update/<alarm_id>', methods=['GET', 'POST'])
@login_required
def update(alarm_id):
    logger.info("Update alarm {} view called by user {}".format(alarm_id, g.user.id))
    return redirect(url_for('users.home'))

@mod.route('/set/<alarm_id>')
@login_required
def set(alarm_id):
    """Basic view to set the current user's requested alarm."""

    alarm = Alarm.query.filter_by(id=alarm_id, owner=g.user).first_or_404()
    if alarm.active:
        flash("That alarm is already set.", 'error')
    else:
        task_manager.processSetAlarm(alarm)
        flash("Alarm set!", 'success')
    return redirect(url_for('users.home'))

@mod.route('/unset/<alarm_id>')
def unset(alarm_id):
    """Basic view to unset the current user's requested alarm."""

    alarm = Alarm.query.filter_by(id=alarm_id, owner=g.user).first_or_404()
    if not alarm.active:
        flash("That alarm is not currently set.", 'error')
    else:
        task_manager.processUnsetAlarm(alarm)
        flash("Alarm unset and turned off.", 'success')
    return redirect(url_for('users.home'))
