from __future__ import unicode_literals
import pytest


def test_apply_config_with_plugins(mocker):
    mod = 'temboardagent.cli.'
    mocker.patch(mod + 'Postgres', autospec=True)
    mocker.patch(mod + 'Application.setup_logging', autospec=True)
    cp = mocker.patch(mod + 'Application.create_plugins', autospec=True)
    mocker.patch(mod + 'Application.update_plugins', autospec=True)
    mocker.patch(mod + 'Application.purge_plugins', autospec=True)
    check_connectivity = mocker.patch(mod + 'check_connectivity',
                                      autospec=True)
    from temboardagent.cli import Application

    app = Application()
    app.config_sources = dict()
    app.config = mocker.Mock(name='config')
    app.config.postgresql = dict()
    cp.return_value = ['plugin']

    app.apply_config()

    assert app.postgres
    assert app.setup_logging.called is True
    assert app.update_plugins.called is True
    assert app.purge_plugins.called is True
    assert check_connectivity.called is True


def test_check_connectivity_ok(mocker):
    sleep = mocker.patch('temboardagent.cli.sleep')
    from temboardagent.cli import check_connectivity
    engine = mocker.Mock(name='engine')
    engine.connect.return_value.__enter__ = mocker.Mock(return_value='foo')
    engine.connect.return_value.__exit__ = mocker.Mock(return_value=True)

    check_connectivity(engine)

    assert engine.connect.called is True
    assert sleep.called is False


def test_check_connectivity_sleep(mocker):
    sleep = mocker.patch('temboardagent.cli.sleep')
    from temboardagent.cli import check_connectivity

    engine = mocker.Mock(name='engine')
    engine.connect.side_effect = Exception("can't connect")

    with pytest.raises(Exception, match="can't connect"):
        check_connectivity(engine)

    assert sleep.called is True
