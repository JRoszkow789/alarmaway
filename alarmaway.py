from __future__ import with_statement
from flask import Flask, render_template, g, request, flash, redirect,\
    url_for, session, _app_ctx_stack
from aa_comm import AlarmAwayTwilioClient
import MySQLdb
import MySQLdb.cursors
import logging
import random
import datetime
import re
from werkzeug import generate_password_hash, check_password_hash
from decorators import requires_login
import constants


app = Flask(__name__)
app.config.from_object('config')


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


def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    return rv


def validate_alarm_time(alarm_time):
    hours, mins = alarm_time.split(':')
    if alarm_time:
        return datetime.time(hour=int(hours), minute=int(mins))
    return None


def validate_phone_number(num):
    rv = PHONE_RE.search(num)
    return None if rv is None else (
        rv.group(1) + rv.group(2) + rv.group(3))


def is_number_unique(num):
    rv = query_db('select phone_id from user_phones where phone_number=%s',
        num, one=True)
    return False if rv is not None else True


def is_email_unique(email):
    rv = query_db('select user_id from users where user_email=%s',
        email, one=True)
    return False if rv is not None else True


def validate_email(email):
    rv = EMAIL_RE.search(email)
    return None if rv is None else rv.group()


def create_new_user(email, pw_hash):
    """Creates a new user and returns the newly created user's id.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        '''insert into users (user_email, user_pw, user_role, user_status)
        values (%s, %s, %s, %s)''', (email, pw_hash, constants.USER,
        constants.NEW))
    new_user_id = cur.lastrowid
    db.commit()
    return new_user_id


def generate_verification_code():
    """Generates a new (pseudo)random 7 digit number string used primarily
    for passing to user and verifying new phone numbers.
    """
    new_ver_code = str(random.randint(1000000, 9999999))
    return new_ver_code


def process_phone_verification(phone_num, ver_code):
    app.logger.debug("function call: process_phone_verification\n" +
                     "WARNING -- NOT IMPLEMENTED")


def check_phone_verification(input_attempt):
    if 'uv_code' not in session:
        return False
    else:
        if int(input_attempt) == int(session['uv_code']):
            session.pop('uv_code')
            return True
    return False


def create_new_phone(owner, num, verified=False):
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


def get_user_phones(user_id, verified=False):
    """Returns a list of all user_phone objects currently in the program's
    database, for which the phone's owner is the supplied user_id. The
    second argument allows specification of whether to return all phone
    records found, or only the verified ones.
    """
    ph = (query_db(
            'select phone_id, phone_number from user_phones where\
            phone_owner=%s and phone_verified=%s', (user_id, 1))
        if verified else query_db(
            'select phone_id, phone_number from user_phones where\
            phone_owner=%s', user_id))
    return ph


def get_phone_number(request_phone_id):
    rv = query_db('select phone_number from user_phones where phone_id=%s',
        request_phone_id, one=True)
    if rv is not None:
        return rv['phone_number']
    return None


def get_user_alarms(user_id):
    rv = query_db(
        'select alarm_id, alarm_phone, alarm_time, alarm_active from alarms\
        where alarm_owner=%s', user_id)
    for v in rv:
        # TODO Fix this, probably will be best to do as a whole revamp to the
        # timing system, either using timezone(s) or using Unix-style time.
        # This time/timedelta/mysqldb crap is stupid as hell
        timedelta_val = v['alarm_time']
        v['alarm_time'] = (datetime.datetime.min + timedelta_val).time()
    return rv



def get_user(user_id):
    user = query_db('''select user_id, user_email, user_role, user_status
        from users where user_id=%s''', user_id, one=True)
    return user if user else None


def create_new_alarm(user_id, phone_id, alarm_time, active=False):
    """Creates a new alarm with the given input and inserts it into the
    database. Also returns the newly created alarm's id.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'insert into alarms (alarm_owner, alarm_phone, alarm_time,\
         alarm_active) values (%s, %s, %s, %s)''', (user_id, phone_id,
         alarm_time, active))
    new_alarm_id = cur.lastrowid
    db.commit()
    app.logger.debug('''new alarm created --\nuser_id: %s\nphone_id: %s\n
                        alarm_time: %s\nactive: %s\nnew_alarm_id: %s''' % (
                        user_id, phone_id, alarm_time, active,
                        new_alarm_id))
    return new_alarm_id


def format_alarm_time(alarm_time):
    return alarm_time.strftime('%I:%M %p')


def format_alarm_status(status):
    return 'ACTIVE' if status else 'INACTIVE'


def format_phone_number(num):
    return "(%s) %s-%s" % (num[:3], num[3:6], num[6:])


#TODO Add redirects for recognized users
@app.route('/')
def home():
    return render_template('welcome.html')


@app.route('/get-started', methods=['GET', 'POST'])
def pre_registration():
    if request.method != 'POST':
        return redirect(url_for('registration'))
    error = None
    numerror = None
    input_alarm = validate_alarm_time(request.form['time'])
    input_phone = validate_phone_number(request.form['phone'])
    if input_alarm is None:
        error = 'Sorry, there was a problem processing your alarm, try again.'
    elif input_phone is None:
        error = 'Please enter a valid phone number.'
    elif not is_number_unique(input_phone):
        error = ('Sorry, that phone number is already registered.')
        numerror = True
    else:
        uv_code = generate_verification_code()
        process_phone_verification(input_phone, uv_code)

        session['uv_code'] = uv_code
        session['user_alarm'] = input_alarm
        session['user_phone'] = input_phone

        return redirect(url_for('registration'))
    return render_template('welcome.html', error=error, numerror=numerror)


@app.route('/register', methods=['GET', 'POST'])
def registration():
    if 'user_id' in session:
        flash('You are already logged in as a registered user!')
        return redirect(url_for('home'))

    error = None
    user_phone = None
    phone_prev_present = True if 'user_phone' in session else False

    if request.method == 'POST':
        if not phone_prev_present:
            user_phone = validate_phone_number(request.form['user_phone'])
            if not is_number_unique(user_phone):
                return render_template(
                    'register-new.html',
                    error='That phone number is already associated with\
                    an Alarm Away account.')
        else:
            user_phone = session.pop('user_phone')

        user_email = validate_email(request.form['user_email'])
        user_password = request.form['user_password']
        if user_email and user_password and is_email_unique(user_email):
            # All input data is sanitized and validated. Create user and phone
            new_user_id = create_new_user(user_email,
                generate_password_hash(user_password))
            new_phone_id = create_new_phone(new_user_id, user_phone)
            app.logger.debug('new user created -- id: %s, phone_id: %s' %
                (new_user_id, new_phone_id))
            session['user_id'] = new_user_id
            return redirect(url_for('home'))
        elif not user_email:
            error = 'Please enter a valid email address.'
        elif not user_password:
            error = 'Please enter a valid password.'
        elif not is_email_unique(user_email):
            error = 'That email address is already registered with Alarm Away.'

    target_template = (
        'register-cont.html' if phone_prev_present else 'register-new.html')
    return render_template(target_template, error=error)


@app.route('/user')
@app.route('/user/view')
def user_home():
    if not 'user_id' in session:
        flash('Must be logged in.')
        return redirect(url_for('home'))
    need_verify_phone=False
    user_id = session['user_id']
    if not get_user_phones(user_id, verified=True):
        need_verify_phone=True
    user_info = query_db('select user_email from users where user_id=%s',
        user_id, one=True)
    user_alarms=get_user_alarms(user_id)
    for alarm in user_alarms:
        alarm['phone_number'] = get_phone_number(alarm['alarm_phone'])
    return render_template(
        'user-account-main.html',
        user_email=user_info['user_email'],
        need_verify_phone=need_verify_phone,
        user_alarm_list=user_alarms)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        flash('You are already logged in!')
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        if not request.form['user_email']:
            error = 'Must enter an email address'
        elif not request.form['user_password']:
            error = 'Must enter a password'
        else:
            login_email = validate_email(request.form['user_email'])
            login_pw = request.form['user_password']
            user = query_db('''select user_id, user_pw from users where
                               user_email=%s''', login_email, one=True)
            if user and check_password_hash(user['user_pw'], login_pw):
                session['user_id'] = user['user_id']
                flash('Successfully logged in')
                return redirect(url_for('user_home'))
            elif user:
                error = "Invalid password"
            else:
                error = "Invalid email address"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    # Should we check/clear these others?
    session.pop('uv_code', None)
    session.pop('user_alarm', None)
    session.pop('user_phone', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route('/checkit')
def admin_panel():
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    elif session['user_id'] != 1:
        flash('You do not have the proper credentials to view this page.')
        return redirect(url_for('home'))

    users = query_db('select * from users')
    alarms = query_db('select * from alarms')
    alarm_events = query_db('select * from alarm_events')
    user_phones = query_db('select * from user_phones')
    responses = query_db('select * from responses')

    return render_template('admin.html', users=users, phones=user_phones,
        alarms=alarms, alarm_events=alarm_events, responses=responses)


@app.route('/new')
def new_alarm():
    return render_template('add-new-alarm.html')


# Add some filters to jinja
app.jinja_env.filters['format_alarm_time'] = format_alarm_time
app.jinja_env.filters['format_alarm_status'] = format_alarm_status
app.jinja_env.filters['format_phone_number'] = format_phone_number
