from celery import Celery
from celery.schedules import crontab
from twilio.rest import TwilioRestClient

celery = Celery('tasks', backend='amqp', broker='amqp://guest@localhost//')

CELERYBEAT_SCHEDULE = {
    'every-minute': {
        'task': 'tasks.callme',
        'schedule': crontab(),
        'args': '8137654975',
    }
}

@celery.task
def hello_there(name):
    return "hello there %s!" % name

@celery.task
def callme(phone):
    client = TwilioRestClient(
        account='AC52113fd0906659e7c6091e1c5d754ac7',
        token='799a5ee66e106ca62f1f2fff8ba24220')
    call = client.calls.create(
        to=phone,
        from_='8133584864',
        url="http://canopyinnovation.com/twresp.xml")
    return call.sid
