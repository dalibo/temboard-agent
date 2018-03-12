import logging.config

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
    from urlparse import urlparse, parse_qs
import json
import sys
from urllib import unquote_plus
import ssl
from temboardsched import taskmanager

from temboardagent.routing import get_routes
from temboardagent.errors import HTTPError
from temboardagent.daemon import set_global_reload, reload_true
from temboardagent import __version__ as temboard_version

logger = logging.getLogger(__name__)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """ Handle requests in a separate thread. """


class RequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler.
    """
    def __init__(self, config, sessions, *args, **kwargs):
        """
        Constructor.
        """
        # Sessions array in shared memory.
        self.sessions = sessions
        # Configuration instance.
        self.config = config
        # HTTP server version.
        self.server_version = "temboard-agent/%s" % temboard_version
        # HTTP request method
        self.http_method = None
        # HTTP query.
        self.query = None
        # HTTP POST content in json format.
        self.post_json = None
        # Call HTTP request handler constructor.
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        """
        Handle HTTP GET requests.
        """
        self.http_method = 'GET'
        self.response()

    def do_POST(self,):
        """
        Handle HTTP POST requests.
        """
        self.http_method = 'POST'
        self.response()

    def do_PUT(self,):
        """
        Handle HTTP PUT requests.
        """
        self.http_method = 'PUT'
        # Nothing to do for now.
        pass

    def do_DELETE(self,):
        """
        Handle HTTP DELETE requests.
        """
        self.http_method = 'DELETE'
        self.response()

    def do_OPTIONS(self,):
        self.send_response(200, "OK")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods',
                         'POST, GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         "X-Requested-With, X-Session, Content-Type")
        self.send_header('Access-Control-Max-Age', '1728000')
        self.end_headers()
        logger.info(self.headers.dict['origin'])

    def log_message(self, format, *args):
        """
        Overrides log_message() for HTTP requests logging with our own logger.
        """
        logger.info("client: %s request: %s" % (
                         self.address_string(),
                         format % args))

    def response(self):
        """
        In charge to call the main routing function and to return its results
        as a valid HTTP response.
        """
        try:
            (code, message) = self.route_request()
        except HTTPError as e:
            code = e.code
            message = e.message
        except Exception as e:
            # This is an unknown error. Just inform there is an internal error.
            code = 500
            message = {'error': "Internal error."}
            logger.error("Internal error: %s" % (str(e)))
        self.send_response(int(code))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(message).encode('utf-8'))

    def route_request(self,):
        """
        Main function in charge to route the incoming HTTP request to the right
        function.
        """
        # Let's parse and prepare url, path, query etc..
        url_parsed = urlparse(self.path, 'http')
        path = url_parsed.path
        splitpath = path.split('/')
        if len(splitpath) == 1:
            raise HTTPError(404, 'Not found.')
        root = splitpath[1]
        self.query = parse_qs(url_parsed.query)
        # Loop on each defined route in the API.
        for route in get_routes():
            urlvars = []
            is_that_route = True
            # Check that HTTP method and url root are matching.
            if route['http_method'] == self.http_method and \
               route['root'] == root:
                pos = 0
                # Check each element in the path.
                for elt in splitpath[1:]:
                    try:
                        if type(route['splitpath'][pos]) is not str:
                            # Then this is a regular expression.
                            res = route['splitpath'][pos].match(elt)
                            if res is not None:
                                # If the regexp matches, we want to get the
                                #  value and append it in urlvars.
                                urlvars.append(unquote_plus(res.group(1)))
                            else:
                                is_that_route = False
                                break
                        else:
                            if route['splitpath'][pos] != elt:
                                is_that_route = False
                                break
                    except IndexError:
                        is_that_route = False
                        break
                    pos += 1
                if is_that_route:
                    if self.http_method == 'POST':
                        # TODO: raise an HTTP error if the content-length is
                        # too large.
                        try:
                            # Load POST content expecting it is in JSON format.
                            post_raw = self.rfile.read(
                                        int(self.headers['Content-Length']))
                            self.post_json = json.loads(
                                                post_raw.decode('utf-8'))
                        except Exception as e:
                            raise HTTPError(400, 'Invalid json format: %s.'
                                                 % (str(e)))
                    http_context = {
                        'headers': self.headers,
                        'query': self.query,
                        'post': self.post_json,
                        'urlvars': urlvars
                    }
                    # Call the right API function.
                    response = getattr(sys.modules[route['module']],
                                       route['function'])(
                                http_context,
                                self.config,
                                self.sessions)
                    return (200, response)

        raise HTTPError(404, 'URL not found.')


def handleRequestsUsing(config, sessions):
    return lambda *args: RequestHandler(config, sessions, *args)


def httpd_run(config, sessions, tm_address):
    """
    Serve HTTP for ever and reload configuration from the conf file on SIGHUP
    signal catch.
    """
    server_address = (config.temboard['address'], config.temboard['port'])
    handler_class = handleRequestsUsing(config, sessions)
    httpd = ThreadedHTTPServer(server_address, handler_class)
    httpd.socket = ssl.wrap_socket(httpd.socket,
                                   keyfile=config.temboard['ssl_key_file'],
                                   certfile=config.temboard['ssl_cert_file'],
                                   server_side=True)
    # We need a timeout here because the code after httpd.handle_request() call
    # is written to handle configuration re-loading and needs to be run
    # periodicaly.
    httpd.timeout = 1
    while True:
        httpd.handle_request()
        if reload_true():
            # SIGHUP caught
            # Try to load configuration from the configuration file.
            try:
                # Reset the global var indicating a SIGHUP signal.
                set_global_reload(False)
                logger.info("SIGHUP signal caught, trying to reload "
                            "configuration.")
                config = config.reload()
                # update configuration for the workers
                taskmanager.set_context(
                    'config',
                    {'plugins': config.plugins.__dict__.get('data'),
                     'temboard': config.plugins.__dict__.get('temboard'),
                     'postgresql': config.plugins.__dict__.get('postgresql'),
                     'logging': config.plugins.__dict__.get('logging')},
                    listener_addr=tm_address,
                )
            except Exception as e:
                logger.exception(e)
                logger.info("Keeping previous configuration.")
                config.setup_logging()
            else:
                config.setup_logging()

                # New RequestHandler using the new configuration.
                httpd.RequestHandlerClass = handleRequestsUsing(config,
                                                                sessions)
                logger.info("Done.")

        # Purge expired sessions if any.
        sessions.purge_expired(3600, logger, config)
