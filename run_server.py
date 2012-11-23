from alarmaway import app
from flask_debugtoolbar import DebugToolbarExtension

app.debug = True
toolbar = DebugToolbarExtension(app)
app.run(host='0.0.0.0')
