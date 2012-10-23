from __future__ import with_statement
from flask import Flask, render_template, g, request, flash, redirect,\
    url_for, session, _app_ctx_stack
from twilio import twiml
from twilio.rest import TwilioRestClient
from aa_comm import AlarmAwayTwilioClient
import MySQLdb
import MySQLdb.cursors
import logging
import random
import datetime
import re
from werkzeug import generate_password_hash, check_password_hash
from apscheduler.scheduler import Scheduler
from apscheduler.jobstores.sqlalchemy_store import SQLAlchemyJobStore
from decorators import requires_login
import constants


app = Flask(__name__)
app.config.from_object('config')


sched = Scheduler()
sched.add_jobstore(
        SQLAlchemyJobStore(app.config['JOBSTORE_DB_URI']),
        'ap_jobstore_db')
sched.start()


PHONE_RE = re.compile(
    r'''^\(?([0-9]{3})\)?[. -]?([0-9]{3})[. -]?([0-9]{4})$''')
EMAIL_RE = re.compile( # Copied from Django EmailValidator source
    r'''(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*'''
    r'''|^"([\001-\010\013\014\016-\037!#-''' +
    r'''\[\]-\177]|\\[\001-011\013\014\016-\177])*"'''
    r''')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$''',
    re.IGNORECASE)


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    top = _app_ctx_stack.top
    if not hasattr(top, 'mysql_db'):
        top.mysql_db = MySQLdb.connect(
            host=app.config['DB_HOST'],
            user=app.config['DB_USER'],
            passwd=app.config['DB_PW'],
            port=app.config['DB_PORT'],
            db=app.config['DATABASE'],
            cursorclass=MySQLdb.cursors.DictCursor)
    return top.mysql_db


@app.teardown_appcontext
def close_database(exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'mysql_db'):
        top.mysql_db.close()


def init_db(pw=None):
    """Creates the database tables. Added password for security."""
    if pw is None or pw != app.config['INIT_DB_PW']:
        return False
    else:
        with app.app_context():
            db = get_db()
            with app.open_resource('schema.sql') as f:
                db.cursor().executemany(f.read(), [])
            db.commit()
        return True

def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    return rv


def get_comm_client():
    top = _app_ctx_stack.top
    if not hasattr(top, 'comm_client'):
        top.comm_client = AlarmAwayTwilioClient(
                account=app.config['TWILIO_ACCOUNT_SID'],
                token=app.config['TWILIO_AUTH_TOKEN'],
                comm_number=app.config['FROM_NUMBER'])
    return top.comm_client


def validate_alarm_time(alarm_time):
    hours, mins = alarm_time.split(':')
    rv = (datetime.time(hour=int(hours),
                        minute=int(mins)) if alarm_time is not None
                                          else None)
    return rv


def validate_phone_number(num):
    rv = PHONE_RE.search(num)
    return None if rv is None else (
            rv.group(1) + rv.group(2) + rv.group(3))


def validate_email(email):
    rv = EMAIL_RE.search(email)
    return None if rv is None else rv.group()


def create_new_user(email, pw_hash):
    """Creates a new user and all the associated things. Returns the
    newly created user's user_thing (id).
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
            "insert into users (user_pw, user_status, user_role) values\
            (%s, %s, %s)", (pw_hash, constants.NEW, constants.USER))
    new_user_id = cur.lastrowid
    app.logger.debug('New user created -- user_id: %s' % new_user_id)
    if new_user_id is None:
        return None
    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (0, 'user', new_user_id))
    new_user_thing_id = cur.lastrowid
    if new_user_thing_id is None:
        return None

    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (new_user_thing_id, 'email', email))
    db.commit()
    return new_user_id


def generate_phone_verification(num, secure=False):
    """Generates a new (pseudo)random 7 digit number string used primarily
    for passing to user and verifying new phone numbers. With the optional
    'secure' argument set to True, returns a two-tuple of the verification
    code string and a hash of the provided phone number + ver_code.
    """
    new_ver_code = str(random.randint(1000000, 9999999))
    if not secure:
        return new_ver_code
    else:
        ver_code_hash = generate_password_hash(new_ver_code + num)
        return (new_ver_code, ver_code_hash)


def check_phone_verification(input_attempt, num,):
    if 'uv_code' not in session:
        return False
    else:
        if check_password_hash(input_attempt + num, session['uv_code']):
            session.pop('uv_code')
            return True
        return False


def add_verified_phone(owner, num):
    db = get_db()
    cur = db.cursor()
    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (owner, 'phone', num))
    new_phone_id = cur.lastrowid
    app.logger.debug('New phone record added: %s' % new_phone_id)
    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (new_phone_id, 'verification', 1))
    db.commit()


def get_user(user_id):
    db = get_db()
    cur = db.cursor()
    user = query_db(
            'select thing_id from aa_things where\
            thing_name=%s and thing_value=%s',
            ('user', user_id), one=True)
    return None if not user else user


def get_user_thing(user_id, id_only=False):
    user_thing = query_db(
            'select thing_id, thing_value from aa_things where\
            thing_name=%s and thing_value=%s', ('user', user_id), one=True)
    if id_only:
        return user_thing['thing_id']
    return user_thing


def log_user_in(user_id):
    g.user = None
    g.user = get_user(user_id)
    session['user_id'] = g.user['thing_id']


def set_user_alarm(user_phone, alarm_time):
    sched.add_cron_job(
        wakeup_call,
        args=[user_phone],
        day_of_week="*",
        hour=alarm_time.hour,
        minute=alarm_time.minute,
        jobstore='ap_jobstore_db')

    snooze_time = add_secs(alarm_time, 180)
    sched.add_cron_job(
        wakeup_text,
        args=[user_phone],
        day_of_week="*",
        hour=snooze_time.hour,
        minute=snooze_time.minute,
        jobstore='ap_jobstore_db')

def wakeup_call(phone):
    """Place a request to the phone service to call the number provided
    by the 'phone' parameter. The call's '_from' telephone number and
    xml response url, 'url', are stored in the app's configuration file.
    """
    client = connect_phone()
    call = client.calls.create(
        to=phone,
        from_=app.config['FROM_NUMBER'],
        url=app.config['CALL_URL'])

def wakeup_text(phone):
    """Place a request to the phone service to send a text message to
    the phone number provided by the 'phone' parameter. The message's
    '_from' telephone number and message body, 'body', are stored in
    the app's configuration file.
    """
    client = connect_phone()
    message = client.sms.messages.create(
        to=('+1%s' % phone),
        from_=app.config['FROM_NUMBER'],
        body=app.config['WAKEUP_MSG_BODY'])


def convert_timedelta_to_time(tm):
    """Hack to change a datetime.timedelta object to a datetime.time
    object. Creates a 'dummy date' and adds the timedelta, then returns
    the result's time component.
    """
    dummy_datetime = datetime.datetime.min + tm
    return dummy_datetime.time()


def add_secs(tm, secs):
    fulldate = datetime.datetime(1, 1, 1, tm.hour, tm.minute, tm.second)
    fulldate = fulldate + datetime.timedelta(0, secs)
    return fulldate.time()


def format_alarm_time(alarm_time):
    return alarm_time.strftime('%I:%M %p')


def format_phone_number(num):
    return "(%s) %s-%s" % (num[:3], num[3:6], num[6:])


#TODO Add redirects for recognized users
@app.route('/')
def home():
    return render_template('welcome.html')


@app.route('/get-started', methods=['GET', 'POST'])
def pre_registration():
    error = None
    if request.method == 'POST':
        input_alarm = validate_alarm_time(request.form['time'])
        input_phone = validate_phone_number(request.form['phone'])
        if input_alarm is None:
            error = 'Sorry, there was a problem processing your alarm,\
                please try again.'
        elif input_phone is None:
            error = 'Please enter a valid phone number.'
        else:
            uv_code, secure_uv_code = generate_phone_verification(
                    input_phone, secure=True)
            session['uv_code'] = secure_uv_code

            client = get_comm_client()
            if not client.live:
                pass
            msg = client.generate_sms_message(
                msg_type=client.ver_msg, args=[uv_code])
            client.send_sms(
                input_phone, msg=('Welcome to Alarm Away! Your\
                verification code is %s. Verify your phone number and\
                say hello to a New Good Morning.' % uv_code))
            session['ui_alarm'] = input_alarm
            session['ui_phone'] = input_phone
            return redirect(url_for('registration'))
    return render_template('welcome.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def registration():
    if not 'ui_phone' in session:
        # TODO
        # TRASH!!!!!
        # Acceptable(BARELY) for dev/design/testing only.
        # This needs to either redirect or provide an acceptable
        # registration alternative for a user with no phone. Or register it
        # as an error and handle that with page state.
        # JUST DO SOMETHING!
        flash('Register for free in seconds!')
    error = None
    if request.method == 'POST':
        input_email = request.form['user_email']
        input_pw = request.form['user_pw']
        input_verification = request.form['user_ver_code']
        if not (input_email and input_pw and input_verification):
            error = 'Please complete all required fields.'
        else:
            # Check user's verification code first to save time and db reads
            user_verification_valid = check_phone_verification(
                    session['ui_phone'], input_verification)
            if not user_verification_valid:
                error = "Invalid verification code. Please try again."
            user_email = validate_email(input_email)
            user_pw_hash = generate_password_hash(input_pw)
            if not user_email:
                error = "Invalid email entry, please check your entry."
            else:
                new_user_id = create_new_user(
                        email=input_email,
                        pw_hash=user_pw_hash)
            if not new_user_id:
                flash(
                    'Sorry, something happened... We have been notified!')
                return redirect(url_for('home'))
            add_verified_phone(
                    owner=get_user_thing(new_user_id, id_only=True),
                    num=session['ui_phone'])
            flash('Successfully registered')
            log_user_in(new_user_id)
            return redirect(url_for('login'))
    return render_template('register.html', error=error)


@app.route('/account')
def user_home():
    if not 'user_id' in session:
        flash('Must be logged in.')
        return redirect(url_for('home'))
    user_phone = session['ui_phone']
    user_alarm = session['ui_alarm']
    return render_template('user-account-main.html',
            user_phone=user_phone, user_alarm=user_alarm)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        flash('You are already logged in!')
        return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        session.pop('user_id', None)
    return redirect(url_for('home'))

# Add some filters to jinja
app.jinja_env.filters['alarm_format'] = format_alarm_time
app.jinja_env.filters['phone_format'] = format_phone_number
