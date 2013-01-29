from flask import Blueprint, render_template

from ..users.decorators import non_login_required

mod = Blueprint('frontend', __name__,)

@mod.route('/')
@non_login_required()
def home():
    return render_template('frontend/index.html')
