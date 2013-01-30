from __future__ import absolute_import
from datetime import datetime

from .. import db
from . import constants as USER

class User(db.Model):

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(70))
    created = db.Column(db.DateTime(timezone=False))
    timezone = db.Column(db.String(50))
    status = db.Column(db.SmallInteger, default=USER.FREE)
    role = db.Column(db.SmallInteger, default=USER.USER)

    def __init__(self, email, password, name=None, timezone=None):
        self.email = email
        self.password = password
        self.timezone = timezone
        self.created = datetime.utcnow()
        if name is None:
            name = self.email.split('@')[0]
        self.name = User.make_unique_name(name)

    def getRole(self):
        return USER.ROLE[self.role]

    def __repr__(self):
        return "<User {}: {}>".format(self.id, self.name)

    @staticmethod
    def make_unique_name(name):
        if not User.query.filter_by(name=name).first():
            return name
        version = 2
        while True:
            new_name = name + str(version)
            if not User.query.filter_by(name=new_name).first():
                break
            version += 1
        return new_name

    def getStatus(self):
        return USER.STATUS[self.status]

