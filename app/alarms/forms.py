from __future__ import absolute_import, division, print_function
from datetime import datetime
from flask.ext.wtf import Form, Required, SelectField

def populate_alarm_times():
    """Returns alarm times in a suitable format for a wtforms SelectField.
    Return format is a list of two-tuples of the format:
        ('HH:MM', 'hh:MM AM-PM') where the HH is 24 hour time,
        the hh is 12 hour time.
    """
    alarm_times = [(None, 'Choose a time'),]
    for hour in range(0, 24):
        for minute in range(0, 60, 10):
            alarm_times.append((
                '%.2d:%.2d' % (hour, minute),
                '%d:%.2d %.2s' % ((
                    hour if hour <= 12 else hour - 12),
                    minute, (
                    'AM' if hour < 12 else 'PM')
                ))
            )
    return alarm_times


class AddUserAlarmForm(Form):
    """
    """
    alarm_time = SelectField('Alarm time', [Required()],
        choices=populate_alarm_times())
    phone_number = SelectField('Phone number', [Required()], coerce=int)

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        stripped_time = (datetime
            .strptime(self.alarm_time.data, '%H:%M')
            .replace(tzinfo=None, second=0, microsecond=0)
            .time()
        )
        if not stripped_time:
            return False

        self.alarm_time.data = stripped_time
        return True

    def __repr__(self):
        return '<AddUserAlarmForm - phones: %s>' % self.phone_number.choices
