import os
from app import app
import unittest
from contextlib import closing
import MySQLdb as msdb


def get_db():
    db = msdb.connect(
        host=app.config['TEST_DB_HOST'],
        user=app.config['TEST_DB_USER'],
        passwd=app.config['TEST_DB_PW'],
        port=app.config['TEST_DB_PORT'],
        db=app.config['TEST_DATABASE'],
        cursorclass=msdb.cursors.DictCursor)
    return db

def initialize_test_db():
    with closing(get_db()) as db:
        with open('schema.sql') as f:
            db.cursor().execute(f.read())
        db.commit()


class AlarmAwayTestCase(unittest.TestCase):

    def setUp(self):
        print 'setUp::AlarmAwayTestCase starting...'
        initialize_test_db()
        self.db = get_db()
        app.config['TESTING'] = True
        self.app = app.test_client()
        print 'setUp::AlarmAwayTestCase complete.'

    def tearDown(self):
        if self.db:
            self.db.close()

    def test_serverup(self):
        print 'test_serverup::test'
        rv = self.app.get('/')
        assert rv.status_code == 200

    def test_no_current_user(self):
        print 'test_no_current_user::STARTING'
        rv = self.app.get('/user/view')
        assert rv.status_code == 302


if __name__ == '__main__':
    unittest.main()
