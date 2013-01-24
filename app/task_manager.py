from __future__ import absolute_import

from app import tasks
from app.users.models import User

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
        alarm.active = True
        self.db.session.add(alarm)
        self.db.session.commit()

    def processUnsetAlarm(self, alarm):
        alarm.active = False
        self.db.session.add(alarm)
        self.db.session.commit()
