from __future__ import absolute_import, unicode_literals
from datetime import datetime

from app import db

class Alarm(db.Model):

    __tablename__ = 'alarms'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Time()
    active = db.Column(db.Boolean)
    created = db.Column(db.DateTime(timezone=False))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('User',
        backref=db.backref('alarms', lazy='dynamic'))
    phone_id = db.Column(db.Integer, db.ForeignKey('phones.id'))
    phone = db.relationship('Phone',
        backref=db.backref('alarms', lazy='dynamic'))

    def __init__(self, time, owner, phone):
        self.time = time
        self.owner = owner
        self.phone = phone
        self.created = datetime.utcnow()
        self.active = False

    def __repr__(self):
        return "<Phone {} ({})>".format(self.number, self.id)
