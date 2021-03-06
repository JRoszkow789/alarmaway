from __future__ import absolute_import, division, print_function
from datetime import datetime, timedelta
import pytz

from .. import db

class Alarm(db.Model):

    __tablename__ = 'alarms'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.Time(timezone=False))
    active = db.Column(db.Boolean)
    created = db.Column(db.DateTime(timezone=False))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('User',
        backref=db.backref('alarms', lazy='dynamic'))
    phone_id = db.Column(db.Integer, db.ForeignKey('phones.id'))
    phone = db.relationship('Phone',
        backref=db.backref('alarms', lazy='dynamic'))

    def __init__(self, time=None, owner=None, phone=None):
        self.time = time.replace(second=0, microsecond=0, tzinfo=None)
        self.owner = owner
        self.phone = phone
        self.created = datetime.utcnow()
        self.active = False

    def get_local(self):
        local_timezone = pytz.timezone(self.owner.timezone)
        utc_timezone = pytz.utc
        alarm_as_utc_datetime = datetime.utcnow().replace(
            hour=self.time.hour,
            minute=self.time.minute,
            tzinfo=utc_timezone,
        )
        alarm_as_local_datetime = local_timezone.normalize(
            alarm_as_utc_datetime)
        return alarm_as_local_datetime.time()

    def getNextRunTime(self, local=False):
        utc_now = datetime.utcnow().replace(
            second=0,
            microsecond=0,
            tzinfo=pytz.utc,
        )
        alarm_time = utc_now.replace(
            hour=self.time.hour,
            minute=self.time.minute,
        )
        if alarm_time < utc_now:
            alarm_time = alarm_time + timedelta(days=1)
        if local:
            owner_timezone = pytz.timezone(self.owner.timezone)
            alarm_time = owner_timezone.normalize(alarm_time)
        return alarm_time

    def __repr__(self):
        return "<Alarm {}: {})>".format(self.id, self.time)
