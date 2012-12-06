import os
import alarmaway
import unittest
from contextlib import closing
import MySQLdb as msdb


def get_db():
    db = msdb.connect(
        host=alarmaway.app.config['TEST_DB_HOST'],
        user=alarmaway.app.config['TEST_DB_USER'],
        passwd=alarmaway.app.config['TEST_DB_PW'],
        port=alarmaway.app.config['TEST_DB_PORT'],
        db=alarmaway.app.config['TEST_DATABASE'],
        cursorclass=msdb.cursors.DictCursor)
    return db

def initialize_test_db():
    with closing(get_db()) as db:
        with open('schema.sql') as f:
            db.cursor().execute(f.read())
        db.commit()


class AlarmAwayTestCase(unittest.TestCase):

    def setUp(self):
        initialize_test_db()
        self.db = get_db()
        alarmaway.app.config['TESTING'] = True
        self.app = alarmaway.app.test_client()

    def tearDown(self):
        if self.db:
            self.db.close()

    def test_serverup(self):
        rv = self.app.get('/')
        assert rv.status_code == 200

    def test_no_current_user(self):
        print self.app.get('/user/view')

if __name__ == '__main__':
    unittest.main()
