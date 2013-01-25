from __future__ import absolute_import, division, print_function
import datetime
from flask import (flash, Flask, g, redirect, render_template,
    request, session, url_for)
from flask.ext.sqlalchemy import SQLAlchemy
import twilio.twiml
from .users.decorators import login_required, non_login_required


app = Flask(__name__)
app.config.from_object('config')

if not app.debug:
    import logging
    try:
        log_file = app.config['LOG_FILE']
    except KeyError:
        log_file = '%s.log' % __name__

    formatter = logging.Formatter('''
        Message type:       %(levelname)s
        Location:           %(pathname)s:%(lineno)d
        Module:             %(module)s
        Function:           %(funcName)s
        Time:               %(asctime)s

        Message:

        %(message)s
        ''')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Ensure a root logger exists
    root_logger = logging.getLogger(__name__)
    root_logger.setLevel(logging.DEBUG)

    loggers = [
        app.logger,
        root_logger,
        logging.getLogger('sqlalchemy'),
        ]
    for logger in loggers:
        logger.addHandler(file_handler)


db = SQLAlchemy(app)

from .celery.task_manager import TaskManager
task_manager = TaskManager()

from app.alarms.models import Alarm
from app.phones.models import Phone
from app.users.models import User
from app.celery.models import ManagedTask

from app.phones.views import mod as phonesModule
app.register_blueprint(phonesModule)
from app.users.views import mod as usersModule
app.register_blueprint(usersModule)
from app.alarms.views import mod as alarmsModule
app.register_blueprint(alarmsModule)

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

@app.route('/')
@non_login_required()
def home():
    return render_template('index.html')

@app.route('/twimlio', methods=['POST'])
def alarm_response():
    from_number = request.values.get('From', None)
    app.logger.debug('sms response received! from: %s, mod: %s' % (
        from_number, from_number[2:]))
    from_number = from_number[2:]
    from_id = get_phone_id(from_number)
    if not from_id:
        generate_join_message(new_number=from_number)
        return
    cur_alarms = get_recent_alarms(from_id)
    app.logger.debug('from_id: %s, cur_alarms: %s' % (
        from_id, (','.join([str(a) for a in cur_alarms]) if cur_alarms else
        'No Current Alarms'
    )))
    if cur_alarms:
        for alarm in cur_alarms:
            turn_off_alarm(alarm)
            schedule_alarm(alarm)
        resp_message = 'Have a nice day!'
    else:
        resp_message = 'No alarms running!'
    resp = twilio.twiml.Response()
    resp.sms(resp_message)
    return str(resp)

@app.route('/checkit')
@login_required
def admin_panel():
    #TODO This should be handled in decorator i think.
    if g.user.email.lower() not in app.config['SUPER_USERS']:
        flash(
            'You do not have the proper credentials to view this page.',
            'error',
        )
        return redirect(url_for('user_home'))

    return render_template('admin.html',
        users=User.query.all(),
        alarms=Alarm.query.all(),
        phones=Phone.query.all(),
        tasks=ManagedTask.query.all(),
    )

# Add some filters to jinja
app.jinja_env.filters['format_alarm_time'] = format_alarm_time
app.jinja_env.filters['format_alarm_status'] = format_alarm_status
app.jinja_env.filters['format_user_date'] = format_user_date
app.jinja_env.filters['format_phone_number'] = format_phone_number
