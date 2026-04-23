from types import SimpleNamespace

from click.testing import CliRunner
from flask import g

from app import db


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.committed = False
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        return SimpleNamespace()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_get_db_reuses_connection(app, monkeypatch):
    fake_connection = FakeConnection()
    connect_calls = []

    def fake_connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return fake_connection

    monkeypatch.setattr("app.db.psycopg.connect", fake_connect)

    with app.app_context():
        first = db.get_db()
        second = db.get_db()

        assert first is fake_connection
        assert second is fake_connection
        assert len(connect_calls) == 1


def test_close_db_closes_connection(app):
    fake_connection = FakeConnection()

    with app.app_context():
        g.db = fake_connection
        db.close_db()

        assert fake_connection.closed is True
        assert "db" not in g


def test_init_db_executes_schema_and_commits(app, monkeypatch):
    fake_connection = FakeConnection()
    monkeypatch.setattr("app.db.get_db", lambda: fake_connection)

    with app.app_context():
        db.init_db()

    assert fake_connection.executed
    assert fake_connection.committed is True


def test_init_db_command_runs_via_cli(app, monkeypatch):
    fake_connection = FakeConnection()
    monkeypatch.setattr("app.db.get_db", lambda: fake_connection)

    runner = CliRunner()
    result = runner.invoke(app.cli, ["init-db"])

    assert result.exit_code == 0
    assert "Database initialized" in result.output
    assert fake_connection.committed is True


def test_reset_db_command_requires_confirmation_flag(app):
    runner = CliRunner()
    result = runner.invoke(app.cli, ["reset-db"])

    assert result.exit_code != 0
    assert "Refusing to reset database without --yes" in result.output


def test_reset_db_command_can_cancel(app, monkeypatch):
    fake_connection = FakeConnection()
    monkeypatch.setattr("app.db.get_db", lambda: fake_connection)

    runner = CliRunner()
    result = runner.invoke(app.cli, ["reset-db", "--yes"], input="n\n")

    assert result.exit_code == 0
    assert "Reset cancelled." in result.output
    assert fake_connection.executed == []


def test_reset_db_command_drops_tables_and_reinitializes(app, monkeypatch):
    fake_connection = FakeConnection()
    monkeypatch.setattr("app.db.get_db", lambda: fake_connection)

    runner = CliRunner()
    result = runner.invoke(app.cli, ["reset-db", "--yes"], input="y\n")

    assert result.exit_code == 0
    assert "Database reset and re-initialized." in result.output
    assert any("DROP TABLE IF EXISTS enquiries" in query for query, _ in fake_connection.executed)
    assert any("DROP TABLE IF EXISTS listings" in query for query, _ in fake_connection.executed)
    assert fake_connection.committed is True
