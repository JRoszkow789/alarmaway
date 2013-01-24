from datetime import datetime
from .. import db

class ManagedTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(70))
    return_id = db.Column(db.String(70))
    started = db.Column(db.DateTime(timezone=False))
    ended = db.Column(db.DateTime(timezone=False))
    alarm_id = db.Column(db.Integer, db.ForeignKey('alarms.id'))
    alarm = db.relationship('Alarm')
    phone_id = db.Column(db.Integer, db.ForeignKey('phones.id'))
    phone = db.relationship('Phone')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User')

    def __init__(self,
            task_id=None,
            return_id=None,
            alarm=None,
            phone=None,
            user=None,
            ):
        self.task_id = task_id
        self.return_id = return_id
        self.alarm = alarm
        self.phone = phone
        self.user = user
        self.started = datetime.utcnow().replace(second=0, microsecond=0, tzinfo=None)
        self.ended = None

    def finish(self):
        self.ended = datetime.utcnow().replace(second=0, microsecond=0, tzinfo=None)
