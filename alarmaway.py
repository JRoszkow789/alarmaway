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
    """Creates a new user and returns the newly created user's id.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute('insert into users (user_email, user_pw,\
            user_role, user_status) values (%s, %s, %s, %s)',
            (email, pw_hash, constants.USER, constants.NEW))
    new_user_id = cur.lastrowid
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


def check_phone_verification(input_attempt):
    if 'uv_code' not in session:
        return False
    else:
        if int(input_attempt) == int(session['uv_code']):
            session.pop('uv_code')
            return True
    return False


def add_user_phone(owner, num, verified=False):
    """Adds a new phone number to the database.
    Properties of the new number include the id of the user who(m?) owns the
    phone number, the number itself, and whether or not it has been verified
    yet. Only verified numbers may be used with the AlarmAway service.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute('insert into user_phones values (%s, %s, %s, %s, %s)',
            (None, owner, num, verified, None))
    new_phone_id = cur.lastrowid
    if new_phone_id:
        db.commit()
        return new_phone_id
    return None


def get_user(user_id):
    user = query_db('select user_id, user_email, user_role, user_status from\
            users where user_id=%s', user_id, one=True)
    return user if user else None


def log_user_in(user_id):
    g.user = None
    user = get_user(user_id)
    if 'user_id' in user:
        g.user = user
        session['user_id'] = g.user['user_id']


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
            uv_code = generate_phone_verification(input_phone)
            session['uv_code'] = uv_code

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
        flash('Register for free in seconds!')
    error = None
    if request.method == 'POST':
        input_email = request.form['user_email']
        input_pw = request.form['user_pw']
        input_verification = request.form['user_ver_code']
        user_verification_valid = check_phone_verification(input_verification)
        if not (input_email and input_pw and input_verification):
            error = 'Please complete all required fields.'
        elif not user_verification_valid:
            error = "Invalid verification code. Please try again."
        else:
            # We checked verification code first to save time and db reads,
            # now validate input.
            user_email = validate_email(input_email)
            user_pw_hash = generate_password_hash(input_pw)
            if not user_email:
                error = "Invalid email entry, please check your entry."
            else:
                new_user_id = create_new_user(
                        email=input_email,
                        pw_hash=user_pw_hash)
                if not new_user_id:
                    flash('Oops, something went wrong. We have been notified!')
                    return redirect(url_for('home'))
                flash('Successfully registered')
                user_phone_added = add_user_phone(
                        new_user_id, session['ui_phone'], verified=True)
                if not user_phone_added:
                    flash("Problems with adding phone number. Not added at\
                            this time, please try again.")
                else:
                    flash("New phone number successfully added!")
                log_user_in(new_user_id)
                return redirect(url_for('user_home'))
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
    error = None
    if request.method == 'POST':
        if not request.form['email']:
            error = 'Must enter an email address'
        elif not request.form['password']:
            error = 'Must enter a password'
        else:
            login_email = validate_email(request.form['email'])
            login_pw = request.form['password']
            user = query_db(
                    'select user_id, user_pw from users where user_email=%s',
                    login_email, one=True)
            if user and check_password_hash(user['user_pw'], login_pw):
                log_user_in(user['user_id'])
                flash('Successfully logged in')
                return redirect(url_for('user_home'))
            elif user:
                error = "Invalid password"
            else:
                error = "Invalid email address"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    if 'user_id' in session:
        session.pop('user_id', None)
    return redirect(url_for('home'))

# Add some filters to jinja
app.jinja_env.filters['alarm_format'] = format_alarm_time
app.jinja_env.filters['phone_format'] = format_phone_number