import os
import unittest

import flask

from config import _basedir
from app import app, db
from app.users.models import User


class AlarmAwayTestCase(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            'sqlite:///' + os.path.join(_basedir, 'test.db'))
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def login(self, email, password, app=None):
        """Attempt to log the user in with the given credentials."""
        if app is None:
            app = self.app
        return app.post('users/login', data=dict(
            email=email,
            password=password,
        ), follow_redirects=True)

    def logout(self, app=None):
        """Log the user out."""
        if app is None:
            app = self.app
        return app.get('/users/logout', follow_redirects=True)

    def test_serverup(self):
        """Verify that the server is running and we get the homepage
        as requested. This also may check for a logged in user assuming
        that they would get redirected to their personal home page.
        """

        rv = self.app.get('/')
        assert rv.status_code == 200

    def test_no_current_user_redirect(self):
        """Basic test to assure we are redirected when attempting
        to visit user homepage. This would signify no logged in user.
        """

        rv = self.app.get('/users/home')
        assert rv.status_code == 302

    def test_make_name(self):
        """Ensures that the user still has a name attribute when not explicitly
        assigned one during creation.
        """
        user = User(email='Joe@canopyinnovation.com', password='password')
        assert user.name == 'Joe'

    def test_make_unique_name(self):
        """Ensures that the user is given a unique name during creation."""
        user = User(email='Joe@canopyinnovation.com', password='password')
        db.session.add(user)
        db.session.commit()
        new_user = User(email='Joe@mydomain.com', password='password')
        db.session.add(new_user)
        db.session.commit()
        assert new_user.name == 'Joe2'
        named_user = User(email='joe@me.com', password='password', name='Joe')
        db.session.add(named_user)
        db.session.commit()
        assert named_user.name != 'Joe'
        assert named_user.name != 'Joe2'

    def test_login_logout(self):
        u_email = 'test@canopyinnovation.com'
        u_pass = 'password'
        rv = self.login(u_email, u_pass)
        assert 'does not exist' in rv.data
        user = User(email=u_email, password=u_pass)
        db.session.add(user)
        db.session.commit()
        rv = self.login(u_email, u_pass)
        assert rv.status_code == 200
        self.logout()
        rv = self.app.get('/users/home')
        assert rv.status_code == 302

if __name__ == '__main__':
    unittest.main()
