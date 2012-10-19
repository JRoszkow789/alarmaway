from alarmaway import app
from flask_debugtoolbar import DebugToolbarExtension


toolbar = DebugToolbarExtension(app)


app.run(host='0.0.0.0')
