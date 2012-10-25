from __future__ import absolute_import

from celery_alarmaway import celery

@celery.task
def add(x, y):
    return x + y

@celery.task
def hello(name=''):
    print 'hello %s' % name
    return 'hello %s' % name
