from __future__ import absolute_import

from celery import Celery

celery = Celery('alarmaway.celery', include=['alarmaway.celery.tasks'],)
celery.config_from_object('celeryconfig')

if __name__ == '__main__':
    celery.start()
