import MySQLdb
from contextlib import closing
from celery import Celery
from datetime import timedelta
import aa_comm
import config

COMM_ACCOUNT_ID = 'AC52113fd0906659e7c6091e1c5d754ac7'
COMM_AT = '799a5ee66e106ca62f1f2fff8ba24220'
COMM_FROM_NUMBER = '8133584864'
CALL_URL = 'http://canopyinnovation.com/twresp.xml'

celery = Celery(
    'scheduler',
    backend='amqp://guest@localhost//',
    broker='amqp://guest@localhost//'
)


def get_db():
    """Opens a new database connection"""
    mysql_db = MySQLdb.connect(
        host='localhost',
        user='alarmaway_app',
        passwd='aAa7seVen7',
        port=3306,
        db='AlarmAway')
    return mysql_db


def query_db(query, args=(), one=False):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute(query, args)
        rv = cur.fetchone() if one else cur.fetchall()
    return rv


class AlarmScheduler:

    def __init__(self):
        self.alarm_messages = [
            ('call', 'Time to Wake Up!'),
            ('text', 'Are you up yet?'),
            ('call', 'Hey! Wake Up! Dont make me call again!'),
            ('text', 'Now are you awake?'),
            ('call', 'This is the last time im calling! WAKE UP NOW!'),
            ('text', 'You better be awake! You are... right?')]

    def set_alarm(self, ref_id, alarm_time, phone_number):
        alarm_asyncs = []
        for typ, msg in self.alarm_messages:
            msg_time = alarm_time + timedelta(seconds=(60*(len(alarm_asyncs))))
            if typ == 'call':
                alarm_asyncs.append(send_user_call.apply_async(
                    args=(msg, phone_number), eta=msg_time))
            else:
                alarm_asyncs.append(send_user_text.apply_async(
                    args=(msg, phone_number), eta=msg_time))

        with closing(get_db()) as db:
            cur = db.cursor()
            for at in alarm_asyncs:
                cur.execute(
                    'insert into job_index values (%s, %s, %s)',
                    (None, ref_id, at.id))
            db.commit()
        return 'Success'

    def unset_alarm(self, ref_id, terminate=False):
        current_job_ids = [row[0] for row in query_db(
            'select job_task_id from job_index where job_parent=%s',
            ref_id)
        ]
        for job_id in current_job_ids:
            celery.AsyncResult(job_id).revoke(terminate=terminate)
        return 'Success'

    def send_message(self, msg, number):
        send_user_text.apply_async(args=(msg, number))

@celery.task
def send_user_call(msg, number):
    comm_client = aa_comm.AlarmAwayTwilioClient(
        COMM_ACCOUNT_ID, COMM_AT, COMM_FROM_NUMBER)
    comm_client.make_call(number,
        'http://canopyinnovation.com/twresp.xml')


@celery.task
def send_user_text(msg, number):
    comm_client = aa_comm.AlarmAwayTwilioClient(
        COMM_ACCOUNT_ID, COMM_AT, COMM_FROM_NUMBER)
    comm_client.send_sms(number, msg)
