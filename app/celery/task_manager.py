from __future__ import absolute_import
import datetime

from . import celery
from . import tasks
from .models import ManagedTask
from ..users.models import User

def get_alarm_schedule(alarm):
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

    #TODO
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
        else:
            from app import db as app_db
            self.db = app_db

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


    def processAlarmResponse(self, alarm):
        print('TaskManager.processAlarmResponse: {}'.format(alarm))
