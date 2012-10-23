from twilio.rest import TwilioRestClient
import twilio.twiml


# Built-in message types
VERIFICATION = 0
WAKEUP = 1
MESSAGE_TYPES = {
    VERIFICATION: 'verification',
    WAKEUP: 'wakeup',
}


class AlarmAwayTwilioClient:
    """Handles all Twilio connections, messages, etc."""


    def __init__(self, account, token, comm_number):
        """Establish a new instance of our modified TwilioRestClient,
        using the provided credentials to connect to the Twilio API.
        """
        self.client = TwilioRestClient(
            account=account, token=token)
        self.from_ = comm_number
        self.live = True if self.client else False
        self.ver_msg = VERIFICATION
        self.wake_msg = WAKEUP

    def generate_sms_message(self, msg=None, msg_type=None, args=[]):
        """Generates and returns an sms message represented in twiml/xml.

        Params

                msg    If provided, the message to be converted. Providing
                       this parameter merits the simplest use of this
                       method, as it simply converts the provided message
                       directly into the twiml response.

           msg_type    If no message is provided to the msg parameter, a
                       reference supplied to msg_type will look for the
                       reference in the clients own information, and
                       use the result as the message. Use of this method
                       requires args to be supplied.

              args     Required arguments for default messages handled
                       by the msg_type parameter.

        """
        print msg, msg_type, args
        if msg is None and (msg_type not in MESSAGE_TYPES or args is []):
            return None
        elif msg is None:
            if msg_type in MESSAGE_TYPES:
                msg = (
                    "Welcome to Alarm Away! Your verification code is %s"
                    % args[0])
        resp = twilio.twiml.Response()
        resp.sms(msg)
        return str(resp)

    def send_sms(self, num, msg):
        sms_message = self.client.sms.messages.create(
                to=num,
                from_=self.from_,
                body=msg)
        return sms_message

    def make_call(num, call_url):
        call = self.client.calls.create(
                to=num,
                from_=self.from_,
                url=call_url)
        return call.sid
