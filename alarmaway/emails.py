from flask.ext.mail import Message
import logging.getLogger

from alarmaway import mail

logger = logging.getLogger("alarmaway")

def send_email(subject,
    recipients=[],
    sender=None,
    body_text=None,
    body_html=None,
    ):
    """Sends an email using the alarmaway Flask-Mail client."""

    msg = Message(subject,
        recipients=recipients,
        sender=sender,
    )

    if body_html is not None:
        msg.html = body_html
    else:
        msg.body = body_text
    logger.info("sending email to {recipients}: {msg}".format(
        recipients=recipients, msg=msg))
    mail.send(msg)
