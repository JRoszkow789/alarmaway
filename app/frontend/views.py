from flask import Blueprint, render_template, request

from ..users.decorators import non_login_required
from ..users.forms import MainRegisterForm

mod = Blueprint('frontend', __name__,)

@mod.route('/')
@non_login_required()
def home():
    form = MainRegisterForm(request.form)
    return render_template('frontend/index.html', form=form)
