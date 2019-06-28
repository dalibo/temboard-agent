from temboardagent.errors import UserError
from temboardagent.routing import RouteSet

from ..pgconf import functions as pgconf_functions


routes = RouteSet(prefix=b'/slowqueries')


@routes.get(b'', check_key=True)
def get_slow_queries(http_context, app):
    with app.postgres.connect() as conn:
        query = """SELECT * FROM pg_track_slow_queries();"""
        conn.execute(query)

    ret = []
    for row in conn.get_rows():
        ret.append(row)
    return ret


@routes.get(b'/reset', check_key=True)
def get_slow_queries_reset(http_context, app):
    with app.postgres.connect() as conn:
        query = """SELECT * FROM pg_track_slow_queries_reset();"""
        conn.execute(query)
    return {'ok': 'done'}


@routes.post(b'/explain', check_key=True)
def post_explain_query(http_context, app):
    sql = http_context['post']['sql']
    format = http_context['post'].get('format', 'text').upper()

    with app.postgres.connect() as conn:
        conn.begin()
        query = """EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT %s)
                   %s;""" % (format, sql)

        conn.execute(query)
        rows = list(conn.get_rows())
        conn.rollback()

    return rows[0]['QUERY PLAN']


@routes.get(b'/settings')
def get_pg_conf(http_context, app):
    # Allow change of pg_track_slow_queries only
    http_context['query']['filter'] = ['pg_track_slow_queries']
    with app.postgres.connect() as conn:
        return pgconf_functions.get_settings(conn, http_context)


@routes.post(b'/settings')
def post_slow_queries(http_context, app):
    # Allow change of pg_track_slow_queries only
    http_context['query']['filter'] = ['pg_track_slow_queries']
    with app.postgres.connect() as conn:
        return pgconf_functions.post_settings(conn, app.config, http_context)


class SlowQueriesPlugin(object):
    PG_MIN_VERSION = 90500

    def __init__(self, app, **kw):
        self.app = app

    def load(self):
        pg_version = self.app.postgres.fetch_version()
        if pg_version < self.PG_MIN_VERSION:
            msg = "%s is incompatible with Postgres below 9.5" % (
                self.__class__.__name__)
            raise UserError(msg)

        self.app.router.add(routes)
        for route in routes:
            print(route)

    def unload(self):
        self.app.router.remove(routes)
