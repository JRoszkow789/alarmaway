from __future__ import with_statement
from flask import Flask, render_template, request, flash, redirect,\
    url_for, session, _app_ctx_stack
import MySQLdb
import MySQLdb.cursors
import logging
import random
from datetime import datetime, timedelta, time
import pytz
import scheduler
import re
from werkzeug import generate_password_hash, check_password_hash
import constants


app = Flask(__name__)
app.config.from_object('config')
sched = scheduler.AlarmScheduler()


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


def validate_email(email):
    rv = EMAIL_RE.search(email)
    return None if rv is None else rv.group()


def validate_phone_number(num):
    rv = PHONE_RE.search(num)
    return None if rv is None else (
        rv.group(1) + rv.group(2) + rv.group(3))


def is_email_unique(email):
    rv = query_db('select user_id from users where user_email=%s',
        email, one=True)
    return False if rv is not None else True


def is_number_unique(num):
    rv = query_db('select phone_id from user_phones where phone_number=%s',
        num, one=True)
    return False if rv is not None else True


def format_alarm_time(alarm_time):
    return alarm_time.strftime('%I:%M %p')


def format_alarm_status(status):
    return 'ACTIVE' if status else 'INACTIVE'


def format_user_status(status):
    return constants.USER_STATUS[status]


def format_user_date(user_date):
    return user_date.strftime('%b %d, %Y')


def format_phone_number(num):
    return "(%s) %s-%s" % (num[:3], num[3:6], num[6:])


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


def alarm_is_recent(alarm_time, alarm_id):
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


def validate_alarm_time(alarm_time):
    hours, mins = alarm_time.split(':')
    if alarm_time:
        return time(hour=int(hours), minute=int(mins))
    return None


def get_timezones():
    return pytz.country_timezones('US')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.info('ERROR 500 -- %s' % error)
    return render_template('500.html'), 500


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('user_home'))
    return render_template('welcome.html', tz_list=get_timezones())


@app.route('/get-started', methods=['POST'])
def pre_registration():
    error = None
    input_tz = request.form['timezone']
    input_phone = validate_phone_number(request.form['phone'])
    if not input_tz:
        error = 'You must specify the timezone which your alarms are set for.'
    elif not input_phone:
        error = 'Please enter a valid phone number.'
    elif not is_number_unique(input_phone):
        error = ('Sorry, that phone number is already registered.')
    else:
        uv_code = generate_verification_code()
        send_phone_verification(input_phone, uv_code)
        session.pop('uv_code', None)
        session['uv_code'] = uv_code
        session.pop('user_alarm', None)
        session.pop('user_phone', None)
        session['user_phone'] = input_phone
        session['user_tz'] = input_tz
        return redirect(url_for('registration'))
    return render_template('welcome.html', error=error)

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
            user_tz = request.form['user_tz']
            if not user_tz:
                return render_template('register-new.html',
                    error="You must select a timezone")
            elif not user_phone:
                return render_template('register-new.html',
                    error = "Please enter a valid phone number")
            elif not is_number_unique(user_phone):
                return render_template('register-new.html',
                    error='Number already associated with an account.')
            else:
                uv_code = generate_verification_code()
                session['uv_code'] = uv_code
                send_phone_verification(user_phone, uv_code)
        else:
            user_phone = session.pop('user_phone')
            user_tz = session.pop('user_tz', None)
        user_email = validate_email(request.form['user_email'])
        user_password = request.form['user_password']
        if user_email and user_password and is_email_unique(user_email):
            # All input data is sanitized and validated. Create user and phone
            new_user_id = create_new_user(user_email,
                generate_password_hash(user_password))
            if not add_new_user_timezone(new_user_id, user_tz):
                flash('Error adding timezone, please try again')
            else:
                session.pop('user_tz', None)
            new_phone_id = create_new_phone(new_user_id, user_phone)
            session['user_id'] = new_user_id
            return redirect(url_for('user_home'))
        elif not user_email:
            error = 'Please enter a valid email address.'
        elif not user_password:
            error = 'Please enter a valid password.'
        else:
            error = 'That email address is already registered with Alarm Away.'
    target_template = (
        'register-cont.html' if phone_prev_present else 'register-new.html')
    return render_template(target_template, tz_list=get_timezones(), error=error)


@app.route('/user')
@app.route('/user/view')
def user_home():
    if not 'user_id' in session:
        flash('Must be logged in.')
        return redirect(url_for('home'))
    need_verify_phone=False
    user_id = session['user_id']
    user_phones = get_user_phones(user_id, verified=False)
    for phone in user_phones:
        if not phone['phone_verified']:
            need_verify_phone=True
    user_info = query_db("""
        select user_id, user_email, user_status, user_register
        from users where user_id=%s
        """, user_id, one=True
    )
    user_alarms = get_user_alarms(user_id, active_only=True)
    user_tz = query_db(
        'select up_value from user_properties where up_user=%s and up_key=%s',(
        user_id, 'user_tz'), one=True
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
        user=user_info,
        need_verify_phone=need_verify_phone,
        user_alarm_list=user_alarms,
        user_phone_list=user_phones
    )


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
        return redirect(url_for('user_home'))

    users = query_db('select * from users')
    alarms = query_db('select * from alarms')
    alarm_events = query_db('select * from alarm_events')
    user_phones = query_db('select * from user_phones')
    responses = query_db('select * from responses')

    return render_template('admin.html', users=users, phones=user_phones,
        alarms=alarms, alarm_events=alarm_events, responses=responses)


@app.route('/alarm/new', methods=['GET', 'POST'])
def new_alarm():
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    error = None
    user_id = session['user_id']
    if request.method == 'POST':
        input_alarm = validate_alarm_time(request.form['time'])
        input_phone = request.form['phone']
        app.logger.debug('input_phone: %s' % input_phone)
        if not input_alarm:
            flash('We have encountered an error processing your alarm. Please try again.')
        elif not input_phone:
            flash('You must select a phone number to be associated with this alarm.')
        else:
            user_tz=query_db("""
                select up_value from user_properties
                where up_user=%s and up_key=%s limit 1
                """, (user_id, 'user_tz'), one=True
            )
            input_alarm = get_utc(input_alarm, user_tz['up_value'])
            new_alarm_id = create_new_alarm(
                user_id, input_phone, input_alarm, active=True)
            flash('Awesome! You set an alarm!')
            return redirect(url_for('set_alarm', alarm_id=new_alarm_id))
    user_phones = get_user_phones(user_id)
    return render_template('add-new-alarm.html', error=error,
        user_phones=user_phones)


@app.route('/alarm/remove/<alarm_id>')
def remove_alarm(alarm_id):
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    elif not verify_alarm_ownership(session['user_id'], alarm_id):
        flash('Error removing alarm. You can only delete your own alarms!')
    elif get_alarm_status(alarm_id):
        flash('That alarm is currently active, you need to unset it first.')
    elif not remove_user_alarm(alarm_id):
        flash('Error removing alarm. Please try again.')
    else:
        flash('Alarm successfully removed.')
    return redirect(url_for('user_home'))


@app.route('/alarm/set/<alarm_id>')
def set_alarm(alarm_id):
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    user_id = session['user_id']
    if not verify_alarm_ownership(user_id, alarm_id):
        flash('Error setting alarm. You can only set your own alarms!')
    elif not set_user_alarm(alarm_id):
        flash('Error setting alarm. Please try again.')
    else:
        flash('Alarm Set!')
    return redirect(url_for('user_home'))


@app.route('/alarm/unset/<alarm_id>')
def unset_alarm(alarm_id):
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    user_id = session['user_id']
    if not verify_alarm_ownership(user_id, alarm_id):
        flash('Error updating alarm. Can only modify your own alarms.')
    elif not unset_user_alarm(alarm_id):
        flash('An error occured, please try again.')
    else:
        flash('Alarm canceled')
    return redirect(url_for('user_home'))


@app.route('/alarm/update/<alarm_id>', methods=['GET', 'POST'])
def update_alarm(alarm_id):
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    error = None
    user_id = session['user_id']
    if not verify_alarm_ownership(user_id, alarm_id):
        flash('Error updating alarm. Can only modify your own alarms.')
        return redirect(url_for('user_home'))
    flash('Page still under construction')
    return redirect(url_for('user_home'))


@app.route('/phone/new', methods=['GET', 'POST'])
def new_phone():
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    elif query_db("""
            select phone_id from user_phones
            where phone_owner=%s and phone_verified=%s
            """, (session['user_id'], 0), one=True):
        flash('You currently have an unverified phone. Please verify first.')
        return redirect(url_for('user_home'))
    error = None
    if request.method == 'POST':
        user_phone = validate_phone_number(request.form['user_phone'])
        if not user_phone:
            error = 'You must enter a valid phone number'
        elif not is_number_unique(user_phone):
            error = 'That phone number is already associated with an account.'
        else:
            uv_code = generate_verification_code()
            session['uv_code'] = uv_code
            send_phone_verification(user_phone, uv_code)
            if create_new_phone(session['user_id'], user_phone):
                flash('Successfully added new phone!')
                return redirect(url_for('user_home'))
            else:
                flash('Error adding new phone. Please try again later.')
    return render_template('add-new-phone.html', error=error)


@app.route('/phone/remove/<phone_id>')
def remove_phone(phone_id):
    if not 'user_id' in session:
        flash('You must be logged in to view this page.')
        return redirect(url_for('login'))
    elif not remove_user_phone(session['user_id'], phone_id):
        flash('An error has occured. Please try again.\
        Remember, you can only modify your own phones.')
    else:
        flash('Successfully removed phone')
    return redirect(url_for('user_home'))


@app.route('/phone/verify', methods=['POST'])
def verify_phone():
    user_id = session['user_id']
    ver_attempt = request.form['ver_attempt']
    if ver_attempt != session['uv_code']:
        flash('Invalid verification code')
    else:
        db = get_db()
        cur = db.cursor()
        if cur.execute("""
                update user_phones set phone_verified=%s where phone_owner=%s
                """, [1, user_id]):
            app.logger.debug('phone_verified for user %s' % user_id)
            db.commit()
            flash('Phone verified!')
            session.pop('uv_code', None)
        else:
            flash('Sorry, an error occured, please try again')
    return redirect(url_for('user_home'))


# Add some filters to jinja
app.jinja_env.filters['format_alarm_time'] = format_alarm_time
app.jinja_env.filters['format_alarm_status'] = format_alarm_status
app.jinja_env.filters['format_user_status'] = format_user_status
app.jinja_env.filters['format_user_date'] = format_user_date
app.jinja_env.filters['format_phone_number'] = format_phone_number
