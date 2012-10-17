"""
    AlarmAway Tests
    ~~~~~~~~~~~~~~~~

    Tests the AlarmAway application
"""
import os
import app
import unittest
import tempfile

class AppTestCase(unittest.TestCase):

    def setUp(self):
        self.db_fd, app.app.config['DATABASE'] = tempfile.mkstemp()
        self.app = app.app.test_client()
        app.init_db('devpass')

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.app.config['DATABASE'])

if __name__ == '__main__':
    unittest.main()
