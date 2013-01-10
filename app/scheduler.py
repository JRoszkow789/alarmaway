import MySQLdb
from contextlib import closing
from celery import Celery
from datetime import timedelta
import aa_comm

celery = Celery('scheduler')

import celeryconfig
celery.config_from_object('celeryconfig')


def get_db():
    """Opens a new database connection"""
    mysql_db = MySQLdb.connect(
        host=celeryconfig.DB_HOST,
        user=celeryconfig.DB_USER,
        passwd=celeryconfig.DB_PW,
        port=celeryconfig.DB_PORT,
        db=celeryconfig.DATABASE)
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
            ('call', None),
            ('text', celeryconfig.MSG1),
            ('call', None),
            ('text', celeryconfig.MSG2),
            ('call', None),
            ('text', celeryconfig.MSG3)]

    def set_alarm(self, ref_id, alarm_time, phone_number):
        alarm_asyncs = []
        for typ, msg in self.alarm_messages:
            msg_time = alarm_time + timedelta(seconds=(240*(len(alarm_asyncs))))
            if typ == 'call':
                alarm_asyncs.append(send_user_call.apply_async(
                    args=(phone_number,), eta=msg_time, expires=msg_time+timedelta(seconds=90)))
            else:
                alarm_asyncs.append(send_user_text.apply_async(
                    args=(msg, phone_number), eta=msg_time, expires=msg_time+timedelta(seconds=120)))

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
def send_user_call(number):
    comm_client = aa_comm.AlarmAwayTwilioClient(
        celeryconfig.COMM_ACCOUNT_ID, celeryconfig.COMM_AT,
        celeryconfig.COMM_FROM_NUMBER
    )
    comm_client.make_call(number,
        'http://canopyinnovation.com/twresp.xml')


@celery.task
def send_user_text(msg, number):
    comm_client = aa_comm.AlarmAwayTwilioClient(
        celeryconfig.COMM_ACCOUNT_ID, celeryconfig.COMM_AT,
        celeryconfig.COMM_FROM_NUMBER
    )
    comm_client.send_sms(number, msg)

@celery.task
def test_add(x, y):
    return x + y
