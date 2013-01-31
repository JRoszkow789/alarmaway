from __future__ import absolute_import

from flask import Blueprint, render_template

from .decorators import admin_required
from ..alarms.models import Alarm
from ..celery.models import ManagedTask
from ..phones.models import Phone
from ..users.models import User

mod = Blueprint('admin', __name__, url_prefix='/checkit')
import logging
logger = logging.getLogger("alarmaway")

@mod.route('/main')
@admin_required
def admin_panel():
    logger.info("admin_panel request approved for user: {}".format(g.user))
    return render_template('admin/main.html',
        users=User.query.all(),
        alarms=Alarm.query.all(),
        phones=Phone.query.all(),
        tasks=ManagedTask.query.all(),
    )

