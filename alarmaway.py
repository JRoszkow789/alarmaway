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
    if pw is None:
        app.logger.warn('init_db called with no password')
        return "Must enter a password."
    elif pw != app.config['INIT_DB_PW']:
        app.logger.warn('init_db called with incorrect password')
        return "Incorrect password. Database initialization failed."
    else:
        app.logger.warn('init_db called with correct password')
        with app.app_context():
            db = get_db()
            with app.open_resource('schema.sql') as f:
                db.cursor().executemany(f.read(), [])
                app.logger.debug('init_db line successfully executed')
            db.commit()
            app.logger.debug('init_db commit_db successful')


def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    return rv


def new_phone_verification(user_id=None):
    """Generates a new (pseudo)random 7 digit number for passing to user
    and verifying new phone numbers.
    """
    # TODO implement or erase the user_id part
    new_ver_code = random.randint(1000000, 9999999)
    return new_ver_code


def get_comm_client():
    top = _app_ctx_stack.top
    if not hasattr(top, 'comm_client'):
        app.logger.debug('new comm_client connection')
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
            (%s, %s, %s)" , (pw_hash, constants.NEW, constants.USER))
    new_user_id = cur.lastrowid
    app.logger.debug('New user created -- user_id: %s' % new_user_id)
    if new_user_id is None:
        return None
    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (new_user_id, 'user', constants.USER))
    new_user_thing_id = cur.lastrowid
    app.logger.debug(
            'New user_thing created -- thing_id: %s' %
            new_user_thing_id)
    if new_user_thing_id is None:
        return None

    # Insert new user email thing
    cur.execute(
            'insert into aa_things (thing_owner, thing_name, thing_value)\
            values (%s, %s, %s)', (new_user_thing_id, 'email', email))
    app.logger.debug(
        'aa_thing created -- thing_id: %s, thing_name: %s' %
        (cur.lastrowid, 'email'))
    db.commit()
    app.logger.debug('create new user: db commit successful')
    return new_user_thing_id


def check_phone_verification(verify_attempt):
    if 'uv_code' not in session:
        app.logger.debug('check_phone_verification -- FAIL: no uv_code')
        return False
    else:
        sesh_ver = session.pop('uv_code', None)
        app.logger.debug(
                'check_phone_verification -- sesh_ver: %s, attempt: %s' %
                (sesh_ver, verify_attempt))
        return int(verify_attempt) == int(sesh_ver)

def add_verified_phone(owner, num):
    app.logger.debug('NOT IMPLEMENTED: add_verified_phone')
    pass


def log_user_in(user_id):
    app.logger.debug('NOT IMPLEMENTED: log_user_in')
    pass


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
    # ??????? return call.sid?????

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
            # User input is valid given context, begin to process a
            # registration. (Hence the name? eh?)
            #
            # the call to new_phone_verification generates a new
            # verification code to be sent to verify the number.
            uv_code = new_phone_verification(user_id=None)
            session['uv_code'] = uv_code

            # Here we grab our current voice/sms client, generate a message
            # to be sent, and "send" the message by adding it to our current
            # job queue. 
            client = get_comm_client()
            if not client.live:
                # TODO handle this kinda job queue asap stuff
                pass
            msg = client.generate_sms_message(
                msg_type=client.ver_msg, args=[uv_code])
            # TODO implement that previously mentioned job queue!
            client.send_sms(
                input_phone, msg=('Welcome to Alarm Away! Your\
                verification code is %s. Verify your phone number and\
                say hello to a New Good Morning.' % uv_code))

            # Verification message handling out of the way, handle pre-reg
            # To save some db writes, store current input data in session
            session['ui_alarm'] = input_alarm
            session['ui_phone'] = input_phone

            return redirect(url_for('registration'))
    return render_template('welcome.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def registration():
    if not 'ui_phone' in session:
        flash('Register for free in seconds!')
        app.logger.warn('registration page -- no ui_phone in session.')
    error = None
    if request.method == 'POST':
        input_email = validate_email(request.form['user_email'])
        input_pw = request.form['user_pw']
        input_verification = check_phone_verification(
                request.form['user_ver_code'])
        app.logger.debug('Registration Data valid -- %s, %s' %
                (input_email, input_verification))
        if input_email is None:
            error = 'You must enter a valid email address.'
        elif input_pw is None:
            error = 'A password is required to create an account.'
        elif not input_verification:
            error = 'Invalid verification code'
        else:
            # All input data is valid, now we can process the new reg
            new_user_id = create_new_user( # Actually new user's thing id
                    email=input_email,
                    pw_hash=generate_password_hash(input_pw))
            if not new_user_id:
                app.logger.error('user registration: all data valid,\
                    new_user_id returned none. Data below: \nemail: %s\n\
                    new_user_id: %s' % (input_email, new_user_id))

            # Add the user's verified phone number to the database
            add_verified_phone(
                    owner=new_user_id,
                    num=session['ui_phone'])

            # Alert user of successful registration, and log them in.
            flash('Successfully registered')
            log_user_in(new_user_id)
            return redirect(url_for('login'))

    return render_template('registration_stage_two.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    return '''

        <h3>Login Page</h3>
        <a href='/'>
            Return to home
        </a>

        '''


@app.route('/logout')
def logout():
    return '''

        <h3>Logout Page</h3>
        <a href='/'>
            Return to home
        </a>

        '''
