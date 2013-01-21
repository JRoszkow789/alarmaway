from __future__ import absolute_import
from datetime import datetime

from app import db

class Phone(db.Model):

    __tablename__ = 'phones'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(10), unique=True)
    verified = db.Column(db.Boolean)
    created = db.Column(db.DateTime(timezone=False))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('User',
        backref=db.backref('phones', lazy='dynamic'))

    def __init__(self, number, owner, verified=False):
        self.number = number
        self.owner = owner
        self.verified = verified
        self.created = datetime.utcnow()

    def __repr__(self):
        return "<Phone %s belonging to user %s>" % (self.number, self.owner.id)
