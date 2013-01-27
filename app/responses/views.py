from __future__ import absolute_import
from flask import Blueprint, request
import logging
import twilio.twiml

from .. import task_manager
from ..phones.models import Phone

mod = Blueprint('responses', __name__, url_prefix='/responses')
mod.logger = logging.getLogger(__name__)
@mod.route('/receive', methods=['POST'])
def alarm_response():
    from_number = request.values.get('From', None)
    mod.logger.debug('sms response received! from: %s, mod: %s' % (
        from_number, from_number[2:]))
    from_number = from_number[2:]
    from_phone = Phone.query.filter_by(number=from_number).first()
    if not from_phone:
        generate_join_message(new_number=from_number)
        return

    alarms = from_phone.alarms.filter_by(active=True).all()
    if not alarms:
        resp_message = 'No alarms running!'
    else:
        for alarm in alarms:
            task_manager.processAlarmResponse(alarm)
        resp_message = 'Great, Have a nice day!'
    resp = twilio.twiml.Response()
    resp.sms(resp_message)
    return str(resp)
