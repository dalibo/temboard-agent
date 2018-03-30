# coding: utf-8

from argparse import Action as ArgAction
from pkg_resources import iter_entry_points
from distutils.util import strtobool
import logging
import os
import pdb
import sys

from .configuration import configparser
from .postgres import Postgres
from .log import setup_logging
from .pluginsmgmt import load_plugins_configurations as load_legacy_plugins
from .errors import UserError
from .configuration import MergedConfiguration, OptionSpec
from . import validators as v
from .version import __version__

logger = logging.getLogger(__name__)


class StoreDefinedAction(ArgAction):
    def __call__(self, parser, namespace, values, option_string=None):
        # Store True if argument is defined.
        if values is None:
            values = True
        setattr(namespace, self.dest, values)


def define_core_arguments(parser):
    parser.add_argument(
        '-c', '--config',
        action='store', dest='temboard_configfile',
        help="Configuration file",
    )
    parser.add_argument(
        '--debug',
        action=StoreDefinedAction, dest='logging_debug', nargs='?',
        metavar='LOGGER,LOGGER,…',
        help=(
            "Shows debug messages for these loggers. "
            "If no loggers defined, debug all core loggers."),
    )
    parser.add_argument(
        '-V', '--version',
        action='version',
        version=__version__
    )


class Application(object):
    # This object contains application context and logic.
    #
    # The core logic is managing configuration and plugins, this is the
    # bootstrap process. Once the app is ready, it owns objects representing
    # the state of the app : config, plugins, etc. Each script or plugin can
    # add an object, it will be shared with other.

    def __init__(self, specs=None, with_plugins='temboardagent.plugins'):
        self.specs = list(specs) if specs else []
        # If `None`, plugin loading is disabled.
        self.with_plugins = with_plugins
        self.plugins = {}
        self.config = MergedConfiguration()
        # This dict stores env, args and parser for hot reloading of
        # configuration.
        self.config_sources = dict()
        self.taskmanager = None

    def __repr__(self):
        return '<%s>' % (self.__class__.__name__)

    def bootstrap(self, args, environ):
        # bootstrapping the app is a complex process to manage options loading
        # incrementally.

        config = self.config
        # Stage 1: Read configfile option
        config.add_specs(self.bootstrap_specs())
        self.config_sources.update(dict(args=args, environ=environ))
        config.load(**self.config_sources)

        # Stage 2: Now read configfile
        parser = configparser.RawConfigParser()
        configfile = config.temboard.configfile
        self.read_file(parser, configfile)
        self.config_sources.update(dict(
            parser=parser, pwd=os.path.dirname(configfile)
        ))

        # Stage 3: Add core and app specific options, load them and apply.
        config.add_specs(self.core_specs())
        config.add_specs(self.specs)
        config.load(**self.config_sources)
        self.apply_config()

        return self.config

    def apply_config(self):
        # Once config is loaded or reloaded, update application state to match
        # new configuration.

        self.setup_logging()
        self.postgres = Postgres(**self.config.postgresql)

        if not self.with_plugins:
            return

        old_plugins = self.purge_plugins()
        new_plugins = self.create_plugins()
        if new_plugins:
            logger.debug("Reading new plugins configuration.")
            self.config.load(**self.config_sources)
        self.update_plugins(old_plugins=old_plugins)

    def bootstrap_specs(self):
        # Generate options specs required for bootstrap from args and environ:
        # configfile.

        s = 'temboard'
        yield OptionSpec(
            s, 'configfile',
            default='/etc/temboard-agent/temboard-agent.conf',
            validator=v.file_,
        )

    def core_specs(self):
        # Generate options specs required for bootstrap from args and environ
        # and file : logging, plugins, postgresql.

        s = 'temboard'
        if self.with_plugins:
            all_plugins = [
                "activity",
                "administration",
                "dashboard",
                "monitoring",
                "pgconf",
            ]
            yield OptionSpec(
                s, 'plugins', default=all_plugins, validator=v.jsonlist,
            )

        s = 'logging'
        yield OptionSpec(s, 'method', default='syslog', validator=v.logmethod)
        yield OptionSpec(s, 'level', default='INFO', validator=v.loglevel)
        yield OptionSpec(
            s, 'facility', default='local0', validator=v.syslogfacility,
        )
        yield OptionSpec(s, 'destination', default='/dev/log')
        yield OptionSpec(s, 'debug', default=False)

        # These options are *core* because they are needed for legacy plugin
        # loading.
        s = 'postgresql'
        yield OptionSpec(
            s, 'host', default='/var/run/postgresql', validator=v.dir_)
        yield OptionSpec(s, 'instance', default='main')
        yield OptionSpec(s, 'port', default=5432, validator=v.port)
        yield OptionSpec(s, 'user', default='postgres')
        yield OptionSpec(s, 'password')
        yield OptionSpec(s, 'dbname', default='postgres')

    def read_file(self, parser, filename):
        logger.info('Reading %s.', filename)
        try:
            with open(filename, 'ro') as fp:
                parser.readfp(fp)
        except IOError as e:
            raise UserError(str(e))

    def fetch_plugin(self, name):
        logger.debug("Looking for plugin %s.", name)
        for ep in iter_entry_points(self.with_plugins, name):
            logger.info("Found plugin %s.", ep)
            try:
                return ep.load()
            except Exception:
                logger.exception("Error while loading %s.", ep)
                raise UserError("Failed to load %s." % (ep.name,))
        else:
            raise UserError("Missing plugin: %s." % (name,))

    def create_plugins(self):
        self.config.plugins = load_legacy_plugins(self.config)

        # Filter legacy plugins
        ng_plugins = filter(
            lambda name: name not in self.config.plugins,
            self.config.temboard.plugins
        )
        # Filter already loaded plugins
        unloaded_names = [
            n for n in ng_plugins
            if n not in self.plugins
        ]

        for name in unloaded_names:
            cls = self.fetch_plugin(name)
            plugin = cls(self)
            self.plugins[name] = plugin
            self.config.plugins.pop(name, None)

        return unloaded_names

    def update_plugins(self, old_plugins=None):
        # Load and unload plugins
        old_names = set(old_plugins or [])
        new_names = set(self.plugins)

        to_unload = old_names - new_names
        for name in to_unload:
            logger.info("Unloading plugin %s.", name)
            old_plugins[name].unload()

        to_load = new_names - old_names
        for name in to_load:
            logger.info("Loading plugin %s.", name)
            self.plugins[name].load()

    def purge_plugins(self):
        old_plugins = self.plugins.copy()
        for name in self.plugins.keys():
            if name in self.config.temboard.plugins:
                continue
            del self.plugins[name]
        return old_plugins

    def reload(self):
        logger.warn("Reloading configuration.")

        # Reset file parser and load values.
        self.config_sources['parser'] = parser = configparser.RawConfigParser()
        self.read_file(parser, self.config.temboard.configfile)
        self.config.load(reload_=True, **self.config_sources)

        self.apply_config()
        logger.info("Configuration reloaded.")
        return self

    def setup_logging(self):
        setup_logging(**self.config.logging)


def bootstrap(args, environ, **kw):
    # Fastpath for simple script without extra context.
    app = Application(**kw)
    app.bootstrap(args=args, environ=environ)
    return app


def detect_debug_mode(environ):
    debug = environ.get('DEBUG', b'0')
    try:
        debug = bool(strtobool(debug))
        if debug:
            environ['TEMBOARD_LOGGING_DEBUG'] = b'__debug__'
    except ValueError:
        environ['TEMBOARD_LOGGING_DEBUG'] = debug
    return debug


def cli(main):
    # A decorator to add consistent CLI behaviour.
    #
    # Decorated function must accept argv and environ arguments and return an
    # exit code.
    #
    # The decorator adds basic logging setup and error management. The
    # decorated function can just raise exception and log using logging module
    # as usual.

    def cli_wrapper(argv=sys.argv[1:], environ=os.environ):
        debug = detect_debug_mode(environ)

        retcode = 1
        try:
            try:
                setup_logging(debug=debug)
                logger.debug("Starting temBoard agent.")
                retcode = main(argv, environ) or 1
            except pdb.bdb.BdbQuit:
                logger.info("Graceful exit from debugger.")
            except UserError as e:
                retcode = e.retcode
                logger.critical("%s", e)
            except Exception:
                logger.exception('Unhandled error:')
                if debug:
                    pdb.post_mortem(sys.exc_info()[2])
                else:
                    logger.error("This is a bug!")
                    logger.error(
                        "Please report traceback to "
                        "https://github.com/dalibo/temboard-agent/issues! "
                        "Thanks!"
                    )
        except KeyboardInterrupt:
            logger.info('Terminated.')
        exit(retcode)
    return cli_wrapper
