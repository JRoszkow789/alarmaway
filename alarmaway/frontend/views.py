from flask import Blueprint, render_template, request

from ..alarms.forms import AddUserAlarmForm
from ..phones.forms import PhoneForm
from ..users.decorators import login_required, non_login_required
from ..users.forms import LoginForm, MainRegisterForm

mod = Blueprint('frontend', __name__,)

@mod.route('/')
@non_login_required()
def home():
    register_form = MainRegisterForm(request.form)
    signin_form = LoginForm(request.form)
    return render_template('frontend/index.html',
        form=register_form,
        signin_form=signin_form,
    )

@mod.route('/firstphone')
@login_required
def add_first_phone():
    form = PhoneForm(request.form)
    return render_template('phones/firstphone.html', form=form)

@mod.route('/firstalarm')
@login_required
def add_first_alarm():
    form = AddUserAlarmForm(request.form)
    return render_template('alarms/firstalarm.html', form=form)
