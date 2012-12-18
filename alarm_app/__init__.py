from flask import Flask, render_template, g, session, _app_ctx_stack
import MySQLdb
import MySQLdb.cursors

from scheduler import AlarmScheduler

app = Flask(__name__)
app.config.from_object('config')
sched = AlarmScheduler()

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    top = _app_ctx_stack.top
    if not hasattr(top, 'mysql_db'):
        top.mysql_db = MySQLdb.connect(
            host=app.config['DB_HOST'],
            user=app.config['DB_USER'],
            passwd=app.config['DB_PW'],
            port=app.config['DB_PORT'],
            db=app.config['DATABASE'],
            cursorclass=MySQLdb.cursors.DictCursor)
    return top.mysql_db



def query_db(query, args=(), one=False):
    """Helper method for establishing db connection and executing query.
       Passes query directly to a mysql cursor object along with supplied args.
       By default, this function returns the list of rows returned by the
       cursor. If the one parameter is set to True, it will return only the
       first result.
    """
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    return rv


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = query_db("""
            select user_id, user_email, user_role, user_status, user_register
            from users where user_id=%s limit 1
            """, session['user_id'], one=True
        )


@app.teardown_appcontext
def close_database(exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'mysql_db'):
        top.mysql_db.close()


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.info('ERROR 500 -- %s' % error)
    return render_template('500.html'), 500


import alarm_app.views
