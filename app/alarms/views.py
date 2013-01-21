from __future__ import absolute_import, division, print_function
import logging
from flask import Blueprint, g, request

from .. import db

mod = Blueprint('alarms', __name__, url_prefix='/alarms')
logger = logging.getLogger('root')

@mod.route('/add', methods=['GET', 'POST'])
def add():
    info_msg = ("""
        VIEW NOT IMPLEMENTED :: alarms.add
        user_id: %s, method type: %s"""
        % (g.user.id, request.method)
        )
    logger.debug(info_msg)
    return info_msg

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
