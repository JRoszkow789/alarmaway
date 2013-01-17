from __future__ import absolute_import, unicode_literals
from datetime import datetime
from app import db
from . import constants as USER

class User(db.Model):

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(70))
    created = db.Column(db.DateTime(timezone=False))
    timezone = db.Column(db.String())
    status = db.Column(db.SmallInteger, default=USER.FREE)
    role = db.Column(db.SmallInteger, default=USER.USER)

    def __init__(self, name, email=None, password=None, timezone=None):
        self.name = name
        self.email = email
        self.password = password
        self.timezone = timezone
        self.joined = datetime.utcnow()

    def getStatus(self):
        return USER.STATUS[self.status]

    def getRole(self):
        return USER.ROLE[self.role]

    def __repr__(self):
        return "<User {} ({})>".format(self.name, self.id)
