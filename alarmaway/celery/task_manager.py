from __future__ import absolute_import
import datetime
import logging

from . import tasks
from .celery import celery
from .models import ManagedTask
from ..users.models import User

logger = logging.getLogger('alarmaway')

def get_alarm_schedule(alarm):
    """Returns a list of datetimes as a "schedule" for the given alarm."""

    now = datetime.datetime.utcnow().replace(tzinfo=None)
    if alarm.time > now.time():
        base_time = now.replace(
            hour=alarm.time.hour,
            minute=alarm.time.minute,
            second=0,
            microsecond=0,
            tzinfo=None,
            )
    else:
        now_tomorrow = now + datetime.timedelta(days=1)
        base_time = now_tomorrow.replace(
            hour=alarm.time.hour,
            minute=alarm.time.minute,
            second=0,
            microsecond=0,
            tzinfo=None,
            )

    #This can probably be done a little nicer/more programatically.
    times = [
        base_time,
        base_time + datetime.timedelta(seconds=180),
        base_time + datetime.timedelta(seconds=480),
        base_time + datetime.timedelta(seconds=660),
        base_time + datetime.timedelta(seconds=960),
        base_time + datetime.timedelta(seconds=1140),
        ]
    return times

class TaskManager:
    def __init__(self, db=None):
        if db is not None:
            self.db = db

    def init_db(self, db):
        self.db = db

    def test_db(self, email=None):
        user = User.query.filter_by(email=email).first()
        tasks.greet(user.name, user.id)

    def processPhoneVerification(self, phone, verification_code):
        message = (
            "Welcome to AlarmAway! Verify this phone using the verification "
            "following verification code: {}"
            .format(verification_code)
            )
        tasks.send_sms_message(phone.id, message)

    def processSetAlarm(self, alarm):
        for count, time in enumerate(get_alarm_schedule(alarm)):
            if count % 2 != 0:
                async_task = tasks.send_sms_message.apply_async(
                    args=(alarm.phone.id, 'Are you up yet?'),
                    eta=time,
                    expires=time+datetime.timedelta(seconds=120),
                )
            else:
                async_task = tasks.send_phone_call.apply_async(
                    args=(alarm.phone.id,),
                    eta=time,
                    expires=time+datetime.timedelta(seconds=120),
                )

            task = ManagedTask(
                task_id=async_task.id,
                alarm=alarm,
            )
            self.db.session.add(task)

        alarm.active = True
        self.db.session.add(alarm)
        self.db.session.commit()


    def processUnsetAlarm(self, alarm):
        tasks = ManagedTask.query.filter_by(alarm=alarm, ended=None).all()
        for task in tasks:
            celery.AsyncResult(task.task_id).revoke(terminate=True)
            task.finish()
            self.db.session.add(task)
        alarm.active = False
        self.db.session.add(alarm)
        self.db.session.commit()


    def processRemoveAlarm(self, alarm):
        logger.info("removing alarm {alarm}".format(alarm=alarm.id))
        tasks = ManagedTask.query.filter_by(alarm=alarm)
        ready_tasks = tasks.filter_by(ended=None)
        tasks = tasks.all()
        ready_tasks = ready_tasks.all()
        if set(ready_tasks) is not set(tasks):
            for t in set(tasks) - set(ready_tasks):
                t.finish()
                logger.info(
                    "remove alarm {alarm}: cleaned up task {task}".format(
                        alarm=alarm.id,
                        task=t.id,
                ))
        for t in tasks:
            logger.info("remove alarm {alarm}: removing task {task}".format(
                alarm=alarm.id,
                task=t.id,
            ))
            self.db.session.delete(t)
        self.db.session.commit()
        self.db.session.delete(alarm)
        self.db.session.commit()


    def processAlarmResponse(self, alarm):
        """Handles the process of unsetting and, if neccessary, resetting
        the given alarm.
        """

        #This is just a stub for now, more functionality coming soon.
        logger.debug("Processing alarm response for alarm {}".format(alarm))
        self.processSetAlarm(alarm)
        self.processUnsetAlarm(alarm)
