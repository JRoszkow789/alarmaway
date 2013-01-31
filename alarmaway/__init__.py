from __future__ import absolute_import, division, print_function
import datetime

from flask import Flask, g, render_template, request, session
from flask.ext.mail import Mail
from flask.ext.sqlalchemy import SQLAlchemy


app = Flask('alarmaway')
app.config.from_object('config')
db = SQLAlchemy(app)
mail = Mail(app)

def setup_logging(app):
    if not app.debug:
        import logging

        #Setup email handling
        from logging.handlers import SMTPHandler
        mail_handler = SMTPHandler(
            host=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr=app.config['MAIL_USERNAME'],
            toaddr=app.config['ADMINS'],
            subject="alarmaway failure",
            credentials=(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD']),
            secure=(),
        )

        mail_formatter = logging.Formatter('''
            Message type:       %(levelname)s
            Location:           %(pathname)s:%(lineno)d
            Module:             %(module)s
            Function:           %(funcName)s
            Time:               %(asctime)s

            Message:

            %(message)s
            ''')
        mail_handler.setFormatter(mail_formatter)
        mail_handler.setLevel(logging.ERROR)

        #Setup File logging
        try:
            log_file = app.config['LOG_FILE']
        except KeyError:
            log_file = 'alarmaway.log'

        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s -- %(module)s.%(funcName)s: '
            '%(message)s '
            '[in %(pathname)s:%(lineno)d]'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)

        # Ensure a root logger exists
        root_logger = logging.getLogger('alarmaway')

        # Add handlers to all known loggers
        loggers = [
            app.logger,
            root_logger,
            logging.getLogger('sqlalchemy'),
        ]
        for logger in loggers:
            logger.addHandler(mail_handler)
            logger.addHandler(file_handler)


setup_logging(app)
from .celery import TaskManager
task_manager = TaskManager()
task_manager.init_db(db)

from .users.models import User


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.filter_by(id=session['user_id']).first()

def format_alarm_time(alarm_time):
    """Formats a datetime.time object for human-friendly output.
       Used within Jinja templates.
    """
    if not isinstance(alarm_time, datetime.time):
        alarm_time = datetime.datetime(alarm_time).time()
    return alarm_time.strftime('%I:%M %p')

def format_alarm_status(status):
    return 'ACTIVE' if status else 'INACTIVE'

def format_user_date(user_date):
    return user_date.strftime('%b %d, %Y')

def format_phone_number(num):
    return "(%s) %s-%s" % (num[:3], num[3:6], num[6:])

@app.errorhandler(404)
def page_not_found(error):
    path = request.path
    app.logger.debug('%s\nPath: %s' % (error, path))
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    app.logger.error(error)
    return render_template('500.html'), 500

# Add some filters to jinja
app.jinja_env.filters['format_alarm_time'] = format_alarm_time
app.jinja_env.filters['format_alarm_status'] = format_alarm_status
app.jinja_env.filters['format_user_date'] = format_user_date
app.jinja_env.filters['format_phone_number'] = format_phone_number


from .phones.views import mod as phonesModule
app.register_blueprint(phonesModule)
from .users.views import mod as usersModule
app.register_blueprint(usersModule)
from .alarms.views import mod as alarmsModule
app.register_blueprint(alarmsModule)
from .responses.views import mod as responsesModule
app.register_blueprint(responsesModule)
from .frontend.views import mod as frontendModule
app.register_blueprint(frontendModule)
from .admin.views import mod as adminModule
app.register_blueprint(adminModule)
