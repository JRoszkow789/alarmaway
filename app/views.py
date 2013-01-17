from . import app

@app.route('/index')
def loggers():
    app.logger.debug('method loggers called in %s' % __name__)
    return "Hello from views.loggers!"
