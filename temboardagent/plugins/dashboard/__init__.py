import logging
import time
import signal
import json
import sys
import collections

from os import getpid
try:
    from configparser import NoOptionError
except ImportError:
    from ConfigParser import NoOptionError

from temboardagent.scheduler import taskmanager
from temboardagent.api_wrapper import (
    api_function_wrapper,
    api_function_wrapper_pg,
)
from temboardagent.spc import connector, error
from temboardagent.routing import add_route, add_worker
from temboardagent.configuration import (
    PluginConfiguration,
    ConfigurationError,
)
from temboardagent.errors import (
    SharedItem_exists,
    SharedItem_no_free_slot_left,
)
from temboardagent.queue import Queue, Message
import dashboard.metrics as metrics


logger = logging.getLogger(__name__)


@add_route('GET', '/dashboard')
def dashboard(http_context,
              config=None,
              sessions=None,
              commands=None):
    """
Get the whole last data set used to render dashboard view. Data have been collected async.

.. sourcecode:: http

    GET /dashboard HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.8
    Date: Wed, 22 Apr 2015 09:57:52 GMT
    Content-type: application/json

    {
        "active_backends":
        {
            "nb": 1,
            "time": 1429617751.29224
        },
        "loadaverage": 0.28,
        "os_version": "Linux 3.16.0-34-generic x86_64",
        "pg_version": "9.4.1",
        "n_cpu": "4",
        "hitratio": 98.0,
        "databases":
        {
            "total_size": "1242 MB",
            "time": "14:02",
            "databases": 4,
            "total_commit": 16728291,
            "total_rollback": 873
        },
        "memory": {
            "total": 3950660,
            "active": 46.9,
            "cached": 20.2,
            "free": 32.9
        },
        "hostname": "neptune",
        "cpu":
        {
            "iowait": 0.0,
            "idle": 97.5,
            "steal": 0.0,
            "user": 2.5,
            "system": 0.0
        },
        "buffers":
        {
            "nb": 348247,
            "time": 1429617751.276508
        }
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.

**Error responses**:

.. sourcecode:: http

    HTTP/1.0 401 Unauthorized
    Server: temboard-agent/0.0.1 Python/2.7.8
    Date: Wed, 22 Apr 2015 09:58:00 GMT
    Content-type: application/json

    {"error": "Invalid session."}


.. sourcecode:: http

    HTTP/1.0 406 Not Acceptable
    Server: temboard-agent/0.0.1 Python/2.7.8
    Date: Wed, 22 Apr 2015 09:58:00 GMT
    Content-type: application/json

    {"error": "Parameter 'X-Session' is malformed."}


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_metrics_queue')


@add_route('GET', '/dashboard/live')
def dashboard_live(http_context,
                   config=None,
                   sessions=None):
    """
Synchronous version of ``/dashboard``. Please refer to ``/dashboard`` API documentation for details.
    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_metrics')


@add_route('GET', '/dashboard/history')
def dashboard_history(http_context,
                      config=None,
                      sessions=None):
    """
Get the last ``n`` sets of dashboard data. ``n`` is defined by parameter ``history_length`` from the ``dashboard`` section of configuration file. Default value is ``150``.

.. sourcecode:: http

    GET /dashboard/history HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 15:56:56 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    [
        {
            "active_backends":
            {
                "nb": 1,
                "time": 1492703660.798522
            },
            "max_connections": 100,
            "databases":
            {
                "total_rollback": 1081,
                "total_size": "158 MB",
                "timestamp": 1492703660.913077,
                "time": "17:54",
                "total_commit": 2825374,
                "databases": 6
            },
            "hostname": "poseidon.home.priv",
            "pg_version": "PostgreSQL 9.5.5 on x86_64-pc-linux-gnu, compiled by x86_64-pc-linux-gnu-gcc (Gentoo 4.9.4 p1.0, pie-0.6.4) 4.9.4, 64-bit",
            "memory":
            {
                "active": 51.0,
                "cached": 29.5,
                "total": 8082124,
                "free": 19.5
            },
            "cpu":
            {
                "iowait": 0.0,
                "idle": 100.0,
                "steal": 0.0,
                "user": 0.0,
                "system": 0.0
            },
            "os_version": "Linux 4.9.6-gentoo-r1",
            "loadaverage": 0.18,
            "hitratio": 99.0,
            "pg_uptime": "01:50:31.573788",
            "pg_port": "5432",
            "n_cpu": 4,
            "pg_data": "/var/lib/postgresql/9.5/data",
            "buffers":
            {
                "nb": 27670,
                "time": 1492703660.784254
            }
        }
    ]

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_history_metrics_queue')


@add_route('GET', '/dashboard/buffers')
def dashboard_buffers(http_context,
                      config=None,
                      sessions=None):
    """
Get the number of buffers allocated by PostgreSQL ``background writer`` process.

.. sourcecode:: http

    GET /dashboard/buffers HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:09:58 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {"buffers": {"nb": 27696, "time": 1492704598.784161}}

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_buffers')


@add_route('GET', '/dashboard/hitratio')
def dashboard_hitratio(http_context,
                       config=None,
                       sessions=None):
    """
Get PostgreSQL global cache hit ratio.

.. sourcecode:: http

    GET /dashboard/hitratio HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:28:33 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {"hitratio": 99.0}

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_hitratio')


@add_route('GET', '/dashboard/active_backends')
def dashboard_active_backends(http_context,
                              config=None,
                              sessions=None):
    """
Get the total number of active backends.

.. sourcecode:: http

    GET /dashboard/active_backends HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:35:55 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "active_backends":
        {
            "nb": 1,
            "time": 1492706155.986045
        }
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_active_backends')


@add_route('GET', '/dashboard/cpu')
def dashboard_cpu(http_context,
                  config=None,
                  sessions=None):
    """
Get CPU usage.

.. sourcecode:: http

    GET /dashboard/cpu HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:40:46 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "cpu":
        {
            "iowait": 0.0,
            "idle": 100.0,
            "steal": 0.0,
            "user": 0.0,
            "system": 0.0
        }
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_cpu_usage')


@add_route('GET', '/dashboard/loadaverage')
def dashboard_loadaverage(http_context,
                          config=None,
                          sessions=None):
    """
System loadaverage.

.. sourcecode:: http

    GET /dashboard/loadaverage HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:44:04 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "loadaverage": 0.06
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.
    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_loadaverage')


@add_route('GET', '/dashboard/memory')
def dashboard_memory(http_context,
                     config=None,
                     sessions=None):
    """
Memory usage.

.. sourcecode:: http

    GET /dashboard/memory HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:46:39 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "memory":
        {
            "active": 50.1,
            "cached": 29.5,
            "total": 8082124,
            "free": 20.4
        }
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_memory_usage')


@add_route('GET', '/dashboard/hostname')
def dashboard_hostname(http_context,
                       config=None,
                       sessions=None):
    """
Machine hostname.

.. sourcecode:: http

    GET /dashboard/hostname HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:48:49 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "hostname": "poseidon.home.priv"
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_hostname')


@add_route('GET', '/dashboard/os_version')
def dashboard_os_version(http_context,
                         config=None,
                         sessions=None):
    """
Operating system version.

.. sourcecode:: http

    GET /dashboard/os_version HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:55:44 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "os_version": "Linux 4.9.6-gentoo-r1"
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_os_version')


@add_route('GET', '/dashboard/pg_version')
def dashboard_pg_version(http_context,
                         config=None,
                         sessions=None):
    """
Get PostgreSQL server version.

.. sourcecode:: http

    GET /dashboard/pg_version HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:59:26 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "pg_version": "PostgreSQL 9.5.5 on x86_64-pc-linux-gnu, compiled by x86_64-pc-linux-gnu-gcc (Gentoo 4.9.4 p1.0, pie-0.6.4) 4.9.4, 64-bit"
    }


:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_pg_version')


@add_route('GET', '/dashboard/n_cpu')
def dashboard_n_cpu(http_context,
                    config=None,
                    sessions=None):
    """
Number of CPU.

.. sourcecode:: http

    GET /dashboard/n_cpu HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 17:03:55 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "n_cpu": 4
    }


:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper(config,
                                http_context,
                                sessions,
                                metrics,
                                'get_n_cpu')


@add_route('GET', '/dashboard/databases')
def dashboard_databases(http_context,
                        config=None,
                        sessions=None):
    """
PostgreSQL cluster size & number of databases.

.. sourcecode:: http

    GET /dashboard/databases HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 17:08:59 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "databases":
        {
            "total_rollback": 1087,
            "total_size": "159 MB",
            "timestamp": 1492708139.981268,
            "databases": 6,
            "total_commit": 2848707,
            "time": "19:08"
        }
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_databases')


@add_route('GET', '/dashboard/info')
def dashboard_info(http_context,
                   config=None,
                   sessions=None):
    """
Get a bunch of global informations about system and PostgreSQL.

.. sourcecode:: http

    GET /dashboard/info HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 17:17:57 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "hostname": "poseidon.home.priv",
        "os_version": "Linux 4.9.6-gentoo-r1",
        "pg_port": "5432",
        "pg_uptime": "03:14:08.029574",
        "pg_version": "PostgreSQL 9.5.5 on x86_64-pc-linux-gnu, compiled by x86_64-pc-linux-gnu-gcc (Gentoo 4.9.4 p1.0, pie-0.6.4) 4.9.4, 64-bit",
        "pg_data": "/var/lib/postgresql/9.5/data"
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.

    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_info')


@add_route('GET', '/dashboard/max_connections')
def dashboard_max_connections(http_context,
                              config=None,
                              sessions=None):
    """
Get the max_connections settings value.

.. sourcecode:: http

    GET /dashboard/active_backends HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.12
    Date: Thu, 20 Apr 2017 16:35:55 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "max_connections": 100
    }

:reqheader X-Session: Session ID
:statuscode 200: no error
:statuscode 401: invalid session
:statuscode 500: internal error
:statuscode 406: header ``X-Session`` is malformed.


    """  # noqa
    return api_function_wrapper_pg(config,
                                   http_context,
                                   sessions,
                                   metrics,
                                   'get_max_connections')


def dashboard_worker_sigterm_handler(signum, frame):
    sys.exit(1)


def collect_data(config):
    try:
        signal.signal(signal.SIGTERM, dashboard_worker_sigterm_handler)
        logger.debug("Collecting data")
        conn = connector(
            host=config['postgresql']['host'],
            port=config['postgresql']['port'],
            user=config['postgresql']['user'],
            password=config['postgresql']['password'],
            database=config['postgresql']['dbname']
        )
        conn.connect()
        # convert config dict to namedtuple
        config_nt = collections.namedtuple(
                        '__config',
                        ['temboard', 'plugins', 'postgresql', 'logging']
                    )(
                        temboard=config['temboard'],
                        plugins=config['plugins'],
                        postgresql=config['postgresql'],
                        logging=config['logging']
                     )
        # Collect data
        data = metrics.get_metrics(conn, config_nt)
        conn.close()

        # We don't want to store notifications in the history.
        data.pop('notifications', None)
        q = Queue('%s/dashboard.q' % (config['temboard']['home']),
                  max_length=(config['plugins']['dashboard']['history_length']
                              +1),
                  overflow_mode='slide'
                  )
        q.push(Message(content=json.dumps(data)))
        logger.debug(data)
        logger.debug("End")
    except (error, Exception) as e:
        logger.error("Could not collect data")
        logger.exception(e)
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(1)


@taskmanager.worker(pool_size=1)
def dashboard_collector_worker(config):
    collect_data(config)


@taskmanager.bootstrap()
def dashboard_collector_bootstrap(context):
    config = context.get('config')

    max_length = config['plugins']['dashboard']['history_length'] + 1
    q = Queue('%s/dashboard.q' % (config['temboard']['home']),
              max_length=max_length,
              overflow_mode='slide')

    # collect the data once
    collect_data(config)

    # then fill the queue with this data
    last_message = q.get_last_message()
    for i in range(max_length):
        q.push(Message(content=json.dumps(last_message)))

    yield taskmanager.Task(
            worker_name='dashboard_collector_worker',
            id='dashboard_collector',
            options={'config': config},
            redo_interval=config['plugins']['dashboard']['scheduler_interval'],
    )


def configuration(config):
    class Configuration(PluginConfiguration):
        def __init__(self, config, *args, **kwargs):
            PluginConfiguration.__init__(self,
                                         config.configfile,
                                         *args,
                                         **kwargs)

            self.plugin_configuration = {
                'scheduler_interval': 2,
                'history_length': 150
            }

            try:
                self.check_section(__name__)
            except ConfigurationError:
                return

            try:
                if not (self.getint(__name__, 'scheduler_interval') > 0 and
                        self.getint(__name__, 'scheduler_interval') < 86400):
                    raise ValueError()
                self.plugin_configuration['scheduler_interval'] = \
                    self.getint(__name__, 'scheduler_interval')
            except ValueError:
                logger.error("%s - configuration error: 'scheduler_interval' "
                             "must be an integer between 0 and 86400 in "
                             "section '%s' in %s." % (
                                 __name__,
                                 self.configfile,
                                 __name__
                                 )
                             )
            except NoOptionError:
                pass

            try:
                if not (self.getint(__name__, 'history_length') > 0 and
                        self.getint(__name__, 'history_length') < 300):
                    raise ValueError()
                self.plugin_configuration['history_length'] = \
                    self.getint(__name__, 'history_length')
            except ValueError:
                logger.error("%s - configuration error: 'histor_length' must "
                             "be an integer between 0 and 300 in section '%s'"
                             " in %s." % (
                                 __name__,
                                 self.configfile,
                                 __name__
                                 )
                             )
            except NoOptionError:
                pass

    c = Configuration(config)
    return c.plugin_configuration
