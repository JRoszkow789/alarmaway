from __future__ import with_statement
from datetime import datetime, timedelta, time
import logging
import random
import re
from flask import Flask, render_template, request, flash, redirect, \
    g, url_for, session, _app_ctx_stack
import MySQLdb
import MySQLdb.cursors
import pytz
import twilio.twiml
from werkzeug import generate_password_hash, check_password_hash
import constants
from decorators import login_required
import scheduler
from forms import RegisterBeginForm, LoginForm, PhoneVerificationForm
from forms import AddUserPhoneForm, FullRegisterForm, RegisterContinueForm

app = Flask(__name__)
app.config.from_object('config')
sched = scheduler.AlarmScheduler()

_master_timezone_list = pytz.country_timezones('US')

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



def query_db(query, args=(), one=False):
    """Helper method for establishing db connection and executing query.
       Passes query directly to a mysql cursor object along with supplied args.
       By default, this function returns the list of rows returned by the
       cursor. If the one parameter is set to True, it will return only the
       first result.
    """
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    return rv


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = query_db("""
            select user_id, user_email, user_role, user_status, user_register
            from users where user_id=%s limit 1
            """, session['user_id'], one=True
        )


@app.teardown_appcontext
def close_database(exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'mysql_db'):
        top.mysql_db.close()


def validate_email(email):
    """Validates an email address to ensure it is a valid format, and returns
       the email address in the correct format for our application.
    """
    rv = EMAIL_RE.search(email)
    return None if rv is None else rv.group()


def validate_phone_number(num):
    """Validates a phone number to ensure it is in a valid format and returns
       the phone number in the correct format for our application.
    """
    rv = PHONE_RE.search(num)
    return None if rv is None else (
        rv.group(1) + rv.group(2) + rv.group(3))


def format_alarm_time(alarm_time):
    """Formats a datetime.time object for human-friendly output.
       Used within Jinja templates.
    """
    return alarm_time.strftime('%I:%M %p')


def format_alarm_status(status):
    return 'ACTIVE' if status else 'INACTIVE'


def format_user_status(status):
    return constants.USER_STATUS[status]


def format_user_date(user_date):
    return user_date.strftime('%b %d, %Y')


def format_phone_number(num):
    return "(%s) %s-%s" % (num[:3], num[3:6], num[6:])

def verify_user_phone(user_id):
    """Updates the specified user's phones to verified.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'update user_phones set phone_verified=%s where phone_owner=%s',
        (1, user_id))
    db.commit()


def create_new_user(email, pw_hash):
    """Creates a new user and returns the newly created user's id.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        insert into users (user_email, user_pw, user_role, user_status)
        values (%s, %s, %s, %s)
        """, (email, pw_hash, constants.USER, constants.FREE)
    )
    new_user_id = cur.lastrowid
    db.commit()
    return new_user_id


def get_user_id(email_address):
    """Looks up a user by their email address, and returns the user's ID."""
    user_info = query_db('select user_id from users where user_email = %s',
        email_address, one=True)
    if user_info:
        return user_info['user_id']
    return None


def add_new_user_timezone(new_user_id, user_tz):
    """Adds a timezone to the database as a user_property.
    """
    if query_db("""
            select up_id from user_properties
            where up_user=%s and up_key=%s
            """, (new_user_id, 'user_tz'), one=True):
        return False
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'insert into user_properties values (%s, %s, %s, %s)', (
        None, new_user_id, 'user_tz', user_tz
    ))
    new_tz_id = cur.lastrowid
    db.commit()
    return new_tz_id


def generate_verification_code():
    """Generates a new (pseudo)random 7 digit number string used primarily
    for passing to user and verifying new phone numbers.
    """
    new_ver_code = str(random.randint(1000000, 9999999))
    return new_ver_code


def send_phone_verification(phone_num, ver_code):
    sched.send_message((
        'Welcome to AlarmAway! Verification code: %s' % ver_code),
        phone_num
    )

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
    """Helper method that returns a list of all user_phone objects currently
    in the program's database, for which the phone's owner is the supplied
    user_id. The second argument allows specification of whether to return all
    phone records found, or only the verified ones.
    """
    if verified:
        phones = query_db("""
            select phone_id, phone_number from user_phones
            where phone_owner=%s and phone_verified=%s
            """, (user_id, 1
        ))
    else:
        phones = query_db("""
            select phone_id, phone_number, phone_verified
            from user_phones where phone_owner=%s
            """, user_id
        )
    return phones


def get_phone_number(request_phone_id):
    """Retrieves a record from the database containing a phone number for
       the requested phone_id. If a record is found, just the value of
       phone_number is returned.
    """
    rv = query_db('select phone_number from user_phones where phone_id=%s',
        request_phone_id, one=True)
    if rv:
        return rv['phone_number']
    return None


def remove_user_phone(user_id, phone_id):
    db = get_db()
    cur = db.cursor()
    if not cur.execute(
            'delete from user_phones where phone_id=%s and phone_owner=%s',
            (phone_id, user_id)):
        return False
    db.commit()
    return True


def get_user_alarms(user_id, active_only=True):
    if active_only:
        alarms = query_db("""
            select alarm_id, alarm_phone, alarm_time, alarm_active from alarms
            where alarm_owner=%s and alarm_active=%s
            """, (user_id, 1
        ))
    else:
        alarms = query_db("""
            select alarm_id, alarm_phone, alarm_time, alarm_active from alarms
            where alarm_owner=%s
            """, user_id
        )
    return alarms


def get_alarm_status(alarm_id):
    """Takes an alarm_id as a parameter and looks up the given alarm's
       corresponding alarm events. Returns 0 or 1, representing the alarm
       having any active alarm_events or having no active events, respectively
    """
    active_alarm_events = query_db("""
        select event_id, event_owner from alarm_events
        where event_owner=%s and event_status=%s limit 1
        """, (alarm_id, 1), one=True)
    return 0 if not active_alarm_events else 1


def create_new_alarm(user_id, phone_id, alarm_time, active=False):
    """Creates a new alarm with the given input and inserts it into the
    database. Also returns the newly created alarm's id.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        insert into alarms (alarm_owner, alarm_phone,
        alarm_time, alarm_active) values (%s, %s, %s, %s)
        """, (user_id, phone_id, alarm_time, active
    ))
    new_alarm_id = cur.lastrowid
    db.commit()
    return new_alarm_id


def remove_user_alarm(alarm_id):
    db = get_db()
    cur = db.cursor()
    if cur.execute('update alarms set alarm_active=%s where alarm_id=%s', (
            0, alarm_id)):
        db.commit()
        return True
    return False


def verify_alarm_ownership(user_id, alarm_id):
    rv = query_db("""
        select alarm_id, alarm_owner from alarms where
        alarm_id=%s and alarm_owner=%s limit 1
        """, (alarm_id, user_id), one=True
    )
    return False if not rv else True


def set_user_alarm(alarm_id):
    alarm_info = query_db("""
        select alarm_id, alarm_phone, alarm_time, alarm_active
        from alarms where alarm_id=%s
        """, alarm_id, one=True
    )
    if not alarm_info['alarm_active']:
        app.logger.debug('set_user_alarm FAIL -- alarm %s inactive', alarm_id)
        return False
    new_event_id = create_alarm_event(alarm_info['alarm_id'])
    if new_event_id and sched.set_alarm(
            new_event_id,
            get_next_run_datetime(get_alarm_time(alarm_info['alarm_time'])),
            get_phone_number(alarm_info['alarm_phone'])):
        app.logger.debug(
            'new alarm scheduled -- alarm_id: %s, event_id: %s' % (
            alarm_info['alarm_id'], new_event_id
        ))
        return True
    return False


def unset_user_alarm(alarm_id):
    cur_event = query_db("""
        select event_id, event_owner, event_status from alarm_events
        where event_owner=%s and event_status=%s
        """, (alarm_id, 1), one=True
    )
    if not cur_event:
        app.logger.debug(
            'unset_user_alarm FAIL -- no event for alarm_id %s' % alarm_id)
        return False
    db = get_db()
    cur = db.cursor()
    if not cur.execute("""
            update alarm_events set event_end=%s, event_status=%s
            where event_id=%s
            """, (datetime.utcnow(), 0, cur_event['event_id'])):
        app.logger.warn('unset_user_alarm update db unsuccessful.')
    else:
        db.commit()
        sched.unset_alarm(cur_event['event_id'])
        return True
    return False


def create_alarm_event(alarm_id):
    # Needs to check that it is/will be the only existing active event for
    # the corresponding alarm. Returns the new event's event_id upon success
    if query_db("""
            select event_id, event_owner, event_status from alarm_events
            where event_owner=%s and event_status=%s
            """, (alarm_id, 1), one=True):
        app.logger.debug(
            'create_alarm_event FAIL - event exists for alarm %s' % alarm_id)
        return False
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'insert into alarm_events (event_owner, event_status) values (%s, %s)',
        (alarm_id, 1
    ))
    new_event_id = cur.lastrowid
    db.commit()
    if not new_event_id:
        return False
    return new_event_id


def get_utc(local_tm, tz):
    """Takes a datetime.time() object and a string representing a timezone,
       and uses this information and the pytz library to convert time to UTC.
    """
    utc_tz = pytz.utc
    utc_now = datetime.utcnow().replace(tzinfo=utc_tz)
    local_tz = pytz.timezone(tz)
    local_now = local_tz.normalize(utc_now)
    local_alarm = local_now.replace(hour=local_tm.hour, minute=local_tm.minute)
    utc_alarm = utc_tz.normalize(local_alarm)
    return utc_alarm.time()


def get_local(utc_time, tz):
    """Takes a datetime.time() object and a string representing a timezone,
       and uses this information and the pytz library to convert this UTC
       time to a local time in the given timezone.
    """
    utc_tz = pytz.utc
    utc_now = datetime.utcnow().replace(tzinfo=utc_tz)
    utc_alarm = utc_now.replace(hour=utc_time.hour, minute=utc_time.minute)
    local_tz = pytz.timezone(tz)
    local_alarm = local_tz.normalize(utc_alarm)
    return local_alarm.time()


def get_alarm_time(alarm_timedelta):
    return (datetime.min + alarm_timedelta).time()


def alarm_is_recent(alarm_time):
    now = datetime.utcnow()
    if not (now.time() > alarm_time > (now - timedelta(seconds=7200)).time()):
        return False
    return True


def get_next_run_datetime(alarm_time):
    now = datetime.utcnow()
    if alarm_time > now.time():
        run_time = datetime(
            year=now.year, month=now.month, day=now.day,
            hour=alarm_time.hour, minute=alarm_time.minute
        )
    else:
        tomorrow = now + timedelta(days=1)
        run_time = datetime(
            year=tomorrow.year, month=tomorrow.month, day=tomorrow.day,
            hour=alarm_time.hour, minute=alarm_time.minute
        )
    return run_time


def get_timezones():
    return _master_timezone_list

def validate_timezone(tz):
    if tz in get_timezones():
        return tz
    return None


def get_phone_id(phone_num):
    phone_info = query_db(
        'select phone_id from user_phones where phone_number=%s' % phone_num,
        one=True
    )
    return phone_info['phone_id'] if phone_info else None


def generate_join_message(new_number):
    #TODO
    sched.send_message(
        'Welcome to AlarmAway! To complete registration, please visit %s' % (
        'JoeRoszkowski.com'), new_number
    )


def get_recent_alarms(phone_id):
    cur_alarms = [
        alarm for alarm in query_db(
        'select alarm_id, alarm_time from alarms where alarm_phone=%s' % (
        phone_id)) if get_alarm_status(alarm['alarm_id'])
    ]
    for alarm in cur_alarms:
        alarm['alarm_time'] = get_alarm_time(alarm['alarm_time'])
        alarm['next_run_time'] = get_next_run_datetime(alarm['alarm_time'])
        alarm['prev_run_time'] = alarm['next_run_time'] - timedelta(days=1)
    return [
        alarm['alarm_id'] for alarm in cur_alarms if (timedelta(seconds=0) < (
        datetime.utcnow() - alarm['prev_run_time']) < timedelta(seconds=3600)
    )]


def turn_off_alarm(alarm_id):
    cur_event = query_db("""
        select event_id, event_owner, event_status from alarm_events
        where event_owner=%s and event_status=%s
        """, (alarm_id, 1), one=True
    )
    if not cur_event:
        app.logger.debug(
            'turn_off_alarm FAIL -- no event for alarm_id %s' % alarm_id
        )
        return
    db = get_db()
    cur = db.cursor()
    if not cur.execute("""
            update alarm_events set event_end=%s, event_status=%s
            where event_id=%s
            """, (datetime.utcnow(), 0, cur_event['event_id'])):
        app.logger.warn('turn_off_alarm update db unsuccessful.')
    else:
        db.commit()
        sched.unset_alarm(cur_event['event_id'])
        return True
    return False


def schedule_alarm(alarm_id):
    alarm_info = query_db("""
        select alarm_id, alarm_phone, alarm_time from alarms where alarm_id=%s
        """, alarm_id, one=True
    )
    new_event_id = create_alarm_event(alarm_info['alarm_id'])
    if new_event_id and sched.set_alarm(
            new_event_id,
            get_next_run_datetime(get_alarm_time(alarm_info['alarm_time'])),
            get_phone_number(alarm_info['alarm_phone'])):
        app.logger.debug(
            'new alarm scheduled -- alarm_id: %s, event_id: %s' % (
            alarm_info['alarm_id'], new_event_id
        ))
        return True
    elif new_event_id:
        app.logger.warn(
            'Error in scheduling new alarm. new_event_id: %s' % new_event_id
        )
    return False



@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.info('ERROR 500 -- %s' % error)
    return render_template('500.html'), 500


@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' in session:
        return redirect(url_for('user_home'))
    form = RegisterBeginForm(request.form)
    if form.validate_on_submit():
        phone_number = validate_phone_number(form.phone_number.data)
        if not phone_number:
            flash('Please enter a valid phone number.', 'error')
        elif get_phone_id(phone_number):
            flash('Sorry, that phone number is already registered.', 'info')
        else:
            uv_code = generate_verification_code()
            send_phone_verification(phone_number, uv_code)
            session['uv_code'] = uv_code
            session['user_phone'] = phone_number
            session['user_tz'] = form.timezone.data
            return redirect(url_for('continue_registration'))
    return render_template('index.html', form=form)


#TODO this is gonna need more error handling somewhere,
#maybe try/except here, or handle errors in functions themselves?
@app.route('/register2', methods=['GET', 'POST'])
def continue_registration():
    form = RegisterContinueForm(request.form)
    if form.validate_on_submit():
        #Form validates the format of the email address, but we need to check
        #that it does not already exist in our system
        user_email = form.email.data
        if get_user_id(user_email) is not None:
            flash('That email address is already registered. Sign in instead.')
            return redirect(url_for('login'))

        new_user_id = create_new_user(
            user_email, generate_password_hash(form.password.data))
        new_tz_id = add_new_user_timezone(
            new_user_id, session.pop('user_tz', None))
        new_phone_id = create_new_phone(
            new_user_id, session.pop('user_phone', None))

        #User, phone, timezone all successfully added. 'Login' the user 
        #by storing their new id in session, and direct to new account page
        app.logger.debug("""
            View::continue_registration - New User Created
            id: %s, email: %s, phone_id: %s, tz_id: %s
            """ % (new_user_id, user_email, new_phone_id, new_tz_id))
        session['user_id'] = new_user_id
        return redirect(url_for('user_home'))
    return render_template('register2.html', form=form)


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


@app.route('/register', methods=['GET', 'POST'])
def registration():
    user_phone = None
    phone_prev_present = True if 'user_phone' in session else False
    if request.method == 'POST':
        if not phone_prev_present:
            user_phone = validate_phone_number(request.form['user_phone'])
            user_tz = request.form['user_tz']
            if not user_tz:
                flash("You must select a timezone", 'error')
                return render_template('register-new.html',
                    tz_list=get_timezones())
            elif not user_phone:
                flash("Please enter a valid phone number", 'error')
                return render_template('register-new.html',
                    tz_list=get_timezones())
            elif get_phone_id(user_phone):
                flash('That number is already associated with an account.',
                    'error')
                return render_template('register-new.html',
                    tz_list=get_timezones())
            else:
                uv_code = generate_verification_code()
                session['uv_code'] = uv_code
                send_phone_verification(user_phone, uv_code)
        else:
            user_phone = session.pop('user_phone')
            user_tz = session.pop('user_tz', None)
        user_email = validate_email(request.form['user_email'])
        user_password = request.form['user_password']
        if user_email and user_password and not get_user_id(user_email):
            # All input data is sanitized and validated. Create user and phone
            new_user_id = create_new_user(user_email,
                generate_password_hash(user_password))
            if not add_new_user_timezone(new_user_id, user_tz):
                flash('Error adding timezone, please try again', 'error')
            else:
                session.pop('user_tz', None)
            new_phone_id = create_new_phone(new_user_id, user_phone)
            session['user_id'] = new_user_id
            return redirect(url_for('user_home'))
        elif not user_email:
            flash('Please enter a valid email address.', 'error')
        elif not user_password:
            flash('Please enter a valid password.', 'error')
        else:
            flash('That email address is already registered with Alarm Away.',
                'error')
    target_template = (
        'register-cont.html' if phone_prev_present else 'register-new.html')
    return render_template(target_template, tz_list=get_timezones())


@app.route('/user')
@app.route('/user/view')
@login_required
def user_home():
    need_verify_phone, verify_form = False, None
    user = g.user
    user_phones = get_user_phones(user['user_id'], verified=False)
    for phone in user_phones:
        if not phone['phone_verified']:
            need_verify_phone = True
            verify_form = PhoneVerificationForm(request.form)
            break
    user_alarms = get_user_alarms(user['user_id'], active_only=True)
    user_tz = query_db(
        'select up_value from user_properties where up_user=%s and up_key=%s', (
        user['user_id'], 'user_tz'), one=True
    )
    for alarm in user_alarms:
        alarm['local_time'] = get_local(
            get_alarm_time(alarm['alarm_time']),
            user_tz['up_value']
        )
        alarm['alarm_status'] = get_alarm_status(alarm['alarm_id'])
        alarm['phone_number'] = get_phone_number(alarm['alarm_phone'])
    return render_template(
        'user-account-main.html',
        user=user,
        need_verify_phone=need_verify_phone,
        form=verify_form,
        user_alarm_list=user_alarms,
        user_phone_list=user_phones
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        flash('You are already logged in!', 'info')
        return redirect(url_for('home'))
    form = LoginForm(request.form)
    if form.validate_on_submit():
        user = query_db('''select user_id, user_pw from users where
                               user_email=%s''', form.email.data, one=True)
        if user and check_password_hash(user['user_pw'], form.password.data):
            session['user_id'] = user['user_id']
            flash('Successfully logged in', 'success')
            return redirect(url_for('user_home'))
        elif user:
            flash("Invalid password", 'error')
        else:
            flash("Invalid email address", 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('uv_code', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route('/checkit')
@login_required
def admin_panel():
    if g.user['user_email'].lower() not in app.config['SUPER_USERS']:
        flash('You do not have the proper credentials to view this page.',
            'error')
        return redirect(url_for('user_home'))

    users = query_db("""
        select user_id, user_email, user_role, user_status, user_register
        from users"""
    )
    alarms = query_db('select * from alarms')
    alarm_events = query_db('select * from alarm_events')
    user_phones = query_db('select * from user_phones')
    user_properties = query_db('select * from user_properties')
    responses = query_db('select * from responses')
    jobs = query_db('select * from job_index')

    return render_template('admin.html', users=users, phones=user_phones,
        alarms=alarms, alarm_events=alarm_events, responses=responses,
        user_properties=user_properties, jobs=jobs)


@app.route('/alarm/new', methods=['GET', 'POST'])
@login_required
def new_alarm():
    user = g.user
    if request.method == 'POST':
        input_alarm = datetime.strptime(request.form['time'], '%H:%M')
        input_phone = request.form['phone']
        if not input_alarm:
            flash('We have encountered an error processing your alarm.' +
                ' Please try again.', 'error')
        elif not input_phone:
            flash('You must select a phone number to be associated with this ' +
                'alarm.', 'error')
        else:
            user_tz=query_db("""
                select up_value from user_properties
                where up_user=%s and up_key=%s limit 1
                """, (user['user_id'], 'user_tz'), one=True
            )
            input_alarm = get_utc(input_alarm.time(), user_tz['up_value'])
            new_alarm_id = create_new_alarm(
                user['user_id'], input_phone, input_alarm, active=True)
            flash('Well Done! You set an alarm!', 'success')
            return redirect(url_for('set_alarm', alarm_id=new_alarm_id))
    user_phones = get_user_phones(user['user_id'])
    return render_template('add-new-alarm.html', user_phones=user_phones)


@app.route('/alarm/remove/<alarm_id>')
@login_required
def remove_alarm(alarm_id):
    if not verify_alarm_ownership(g.user['user_id'], alarm_id):
        flash('Cannot remove alarm. You can only delete your own alarms!',
            'error')
    elif get_alarm_status(alarm_id):
        flash('That alarm is currently active, you need to unset it first.',
            'error')
    elif not remove_user_alarm(alarm_id):
        flash('Error removing alarm. Please try again.', 'error')
    else:
        flash('Alarm successfully removed.', 'success')
    return redirect(url_for('user_home'))


@app.route('/alarm/set/<alarm_id>')
@login_required
def set_alarm(alarm_id):
    user = g.user
    if not verify_alarm_ownership(user['user_id'], alarm_id):
        flash('Error setting alarm. You can only set your own alarms!', 'error')
    elif not set_user_alarm(alarm_id):
        flash('Error setting alarm. Please try again.', 'error')
    else:
        flash('Alarm Set!', 'success')
    return redirect(url_for('user_home'))


@app.route('/alarm/unset/<alarm_id>')
@login_required
def unset_alarm(alarm_id):
    user = g.user
    if not verify_alarm_ownership(user['user_id'], alarm_id):
        flash('Error updating alarm. Can only modify your own alarms.', 'error')
    elif not unset_user_alarm(alarm_id):
        flash('An error occured, please try again.', 'error')
    else:
        flash('Alarm canceled', 'info')
    return redirect(url_for('user_home'))


@app.route('/alarm/update/<alarm_id>', methods=['GET', 'POST'])
@login_required
def update_alarm(alarm_id):
    user = g.user
    if not verify_alarm_ownership(user['user_id'], alarm_id):
        flash('Error updating alarm. Can only modify your own alarms.', 'error')
        return redirect(url_for('user_home'))
    flash('Page still under construction', 'info')
    return redirect(url_for('user_home'))


@app.route('/phone/new', methods=['GET', 'POST'])
@login_required
def new_phone():
    user = g.user
    if query_db("""
            select phone_id from user_phones
            where phone_owner=%s and phone_verified=%s
            """, (user['user_id'], 0), one=True):
        flash('You currently have an unverified phone. Please verify first.',
            'error')
        return redirect(url_for('user_home'))
    form = AddUserPhoneForm(request.form)
    if form.validate_on_submit():
        phone_number = validate_phone_number(form.phone_number.data)
        if not phone_number:
            flash('You must enter a valid phone number', 'error')
        elif get_phone_id(phone_number):
            flash('That phone number is already associated with an account.',
                'error')
        else:
            uv_code = generate_verification_code()
            session['uv_code'] = uv_code
            send_phone_verification(phone_number, uv_code)
            if create_new_phone(user['user_id'], phone_number):
                flash('Successfully added new phone!', 'success')
                return redirect(url_for('user_home'))
            else:
                flash('Error adding new phone. Please try again later.',
                    'error')
    return render_template('add-new-phone.html', form=form)


@app.route('/phone/remove/<phone_id>')
@login_required
def remove_phone(phone_id):
    if not remove_user_phone(g.user['user_id'], phone_id):
        flash('An error has occured. Please try again.\
        Remember, you can only modify your own phones.', 'error')
    else:
        flash('Successfully removed phone', 'success')
    return redirect(url_for('user_home'))


@app.route('/phone/verify', methods=['POST'])
@login_required
def verify_phone():
    form = PhoneVerificationForm(request.form)
    if form.validate_on_submit():
        correct_code = session.get('uv_code', None)
        if correct_code is None:
            flash('An Error has occured, please request a new code.', 'error')
        elif form.verification_code.data != correct_code:
            flash('Invalid verification code. Try again or request a new code',
                'error')
        else:
            verify_user_phone(g.user['user_id'])
    return redirect(url_for('user_home'))


# Add some filters to jinja
app.jinja_env.filters['format_alarm_time'] = format_alarm_time
app.jinja_env.filters['format_alarm_status'] = format_alarm_status
app.jinja_env.filters['format_user_status'] = format_user_status
app.jinja_env.filters['format_user_date'] = format_user_date
app.jinja_env.filters['format_phone_number'] = format_phone_number
