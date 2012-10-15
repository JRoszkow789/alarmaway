from flask import Flask, render_template, g, request, flash, redirect,\
    url_for, session, _app_ctx_stack
from twilio import twiml
from twilio.rest import TwilioRestClient
import MySQLdb
import MySQLdb.cursors
import logging
import random
import datetime
import re
from werkzeug import generate_password_hash, check_password_hash
from apscheduler.scheduler import Scheduler


app = Flask(__name__)
app.config.from_object('config')


sched = Scheduler()
sched.start()


PHONE_RE = re.compile(r"^\(?([0-9]{3})\)?[. -]?([0-9]{3})[. -]?([0-9]{4})$")
EMAIL_RE = re.compile( # Copied from Django EmailValidator source
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'
    r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$',
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
        app.logger.debug('db connection established')
    return top.mysql_db


@app.teardown_appcontext
def close_database(exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'mysql_db'):
        top.mysql_db.close()
        app.logger.debug('db connection closed')


def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    # Is this ok?
    if one and 'alarm_time' in rv.keys():
        rv['alarm_time'] = (datetime.datetime.min +
                            rv['alarm_time']).time()
    elif not one:
        for row in rv:
            if 'alarm_time' in row.keys():
                row['alarm_time'] = (datetime.datetime.min +
                                     row['alarm_time']).time()
    return rv


def generate_verification_code():
    return random.randint(1000000, 9999999)


def connect_phone():
    return TwilioRestClient(
        account=app.config['TWILIO_ACCOUNT_SID'],
        token=app.config['TWILIO_AUTH_TOKEN'])


def validate_alarm_time(alarm_time):
    hours, mins = alarm_time.split(':')
    rv = (datetime.time(hour=int(hours),
                        minute=int(mins)) if alarm_time is not None
                                          else None)
    app.logger.debug('alarm_time validation result: %s' % rv)
    return rv


def validate_phone_number(num):
    rv = PHONE_RE.search(num)
    return None if rv is None else (
            rv.group(1) + rv.group(2) + rv.group(3))


def validate_email(email):
    return False if email is None else True


def format_alarm(alarm):
    return str(alarm)

def set_user_alarm(user_phone, alarm_time):
    sched.add_cron_job(
        wakeup_call,
        args=[user_phone],
        day_of_week="*",
        hour=alarm_time.hour,
        minute=alarm_time.minute)

    snooze_time = add_secs(alarm_time, 180)
    app.logger.debug(
        'alarm: %s, snooze: %s' %
        (alarm_time, snooze_time))
    sched.add_cron_job(
        wakeup_text,
        args=[user_phone],
        day_of_week="*",
        hour=snooze_time.hour,
        minute=snooze_time.minute)


def wakeup_call(phone):
    app.logger.debug('wakeup_call!')
    client = connect_phone()
    call = client.calls.create(
        to=phone,
        from_=app.config['FROM_NUMBER'],
        url=app.config['CALL_URL'])
    app.logger.debug(call.sid)


def wakeup_text(phone):
    client = connect_phone()
    message = client.sms.messages.create(
        to=('+1%s' % phone),
        from_=app.config['FROM_NUMBER'],
        body=('Good Morning! Are you awake yet?'))


def add_secs(tm, secs):
    fulldate = datetime.datetime(1, 1, 1, tm.hour, tm.minute, tm.second)
    fulldate = fulldate + datetime.timedelta(0, secs)
    return fulldate.time()


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = query_db(
            'select user_id, email from users where user_id=%s',
            session['user_id'], one=True)


@app.route('/', methods=['GET', 'POST'])
def homepage():
    app.logger.debug('homepage')
    if request.method == 'POST':
        # Retrieve the user's input values and validate them
        input_alarm_time = validate_alarm_time(request.form['time'])
        input_phone = validate_phone_number(request.form['phone'])
        input_agrees = request.form['agrees']

        if input_phone is None:
            flash('Invalid phone number')
        elif input_alarm_time is None:
            flash('invalid alarm time')
        elif input_agrees is None:
            flash('you must agree to the terms and conditions to continue.')
        else:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                'insert into users (primary_phone) values (%s)',
                [input_phone])
            created_user_id = cur.lastrowid
            cur.execute(
                'insert into alarms (parent_id, active, alarm_time)\
                values (%s, %s, %s)',
                [created_user_id, 0, input_alarm_time])
            db.commit()
            app.logger.debug(
                'user successfully created, id: %s' %
                created_user_id)
            session['user_id'] = created_user_id
            client = connect_phone()
            ver_code = generate_verification_code()
            message = client.sms.messages.create(
                to=('+1%s' % input_phone),
                from_='+18133584864',
                body=(
                    'Welcome to Are You Up! Your verification code is: %s' %
                    ver_code))
            session['ver_code'] = ver_code
            flash('great!, check your phone for a verification code!')
            return redirect(url_for('verify'))
    return render_template('welcome.html')


@app.route('/almost-there', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        input_email = request.form['user_email']
        app.logger.debug('user email: %s' % input_email)
        input_pw = request.form['user_pw']
        app.logger.debug('user pw: %s' % input_pw)
        input_ver =int( request.form['user_ver_code'])
        app.logger.debug('user ver input: %s' % input_ver)

        if not validate_email(input_email):
            flash('invalid email')
        elif input_pw is None:
            flash('You must enter a password!')
        elif input_ver != session['ver_code']:
            flash('invalid verification code')
            app.logger.debug(
                'ver code failed -- entry: %s, type: %s, stored: %s,\
                type: %s' %
                (input_ver, type(input_ver),
                session['ver_code'], type(session['ver_code'])))
        else:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                'update users set email=%s, pw_hash=%s where user_id=%s',
                [input_email, generate_password_hash(input_pw),
                session['user_id']])
            cur.execute(
                'update alarms set active=%s where parent_id=%s',
                [1, session.get('user_id')])
            db.commit()
            app.logger.debug('email and pw successfully added!')
            alarm_time = query_db(
                'select alarm_time from alarms where parent_id=%s',
                session['user_id'], one=True)['alarm_time']
            user_phone = query_db(
                'select primary_phone from users where user_id=%s',
                g.user['user_id'], one=True)['primary_phone']
            set_user_alarm(user_phone, alarm_time)
            app.logger.debug('alarm set')
            flash('welcome!')
            session.pop('ver_code', None)
            return redirect(url_for('profile'))
    return render_template('almostthere.html')


@app.route('/profile')
def profile():
    if not g.user:
        flash('sorry, must be registered for that page!')
        return redirect(url_for('homepage'))
    else:
        member_since = query_db(
            'select join_date from users where user_id=%s',
            g.user['user_id'], one=True)
        user_alarm = query_db(
            'select alarm_time from alarms where parent_id=%s',
            g.user['user_id'], one=True)
        user_alarm = (format_alarm(user_alarm['alarm_time'])
            if user_alarm else None)
        return render_template('profile.html',
                                user_alarm=user_alarm,
                                member_since=member_since['join_date'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        flash('You are already logged in!')
        return redirect(url_for('profile'))
    elif request.method == 'POST':
        user = query_db(
            'select %s, %s from users where email=%s',
            ('user_id', 'pw_hash', request.form['email']), one=True)
        app.logger.debug('user: %s' % user)
        if user is None:
            flash('Invalid user name')
        elif not check_password_hash(user['pw_hash'],
                                     request.form['password']):
            flash('invalid password')
        else:
            flash('You were successfully logged in')
            session['user_id'] = user['user_id']
            return redirect(url_for('profile'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        session.pop('user_id', None)
    return redirect(url_for('homepage'))
