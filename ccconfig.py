from email_config import (EMAIL_USE_TLS, EMAIL_HOST, EMAIL_PORT,
    EMAIL_USE_SSL, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
from config import DB_HOST, DB_USER, DB_PORT, DB_PW, DATABASE

BROKER_URL = "amqp://guest@localhost:5672//"
CELERY_IMPORTS = "scheduler"
CELERY_RESULT_BACKEND = "amqp://guest@localhost//"
CELERYD_STATE_DB = "aa_worker_state"
CELERY_SEND_TASK_ERROR_EMAILS = True
ADMINS = [('Webmaster', 'webmaster@canopyinnovation.com')]

# Comm Config
COMM_ACCOUNT_ID = 'AC52113fd0906659e7c6091e1c5d754ac7'
COMM_AT = '799a5ee66e106ca62f1f2fff8ba24220'
COMM_FROM_NUMBER = '8133584864'
CALL_URL = 'http://canopyinnovation.com/twresp.xml'
MSG1 = "DEMO - Good morning! Are you awake?"
MSG2 = "DEMO - This is my second time trying to reach you, are you up yet?"
MSG3 = "DEMO - Hey! I'm done trying to get a hold of you! WAKE UP!"
