import pytest

from app import create_app


def test_create_app_uses_instance_config_when_no_test_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "env-secret")
    monkeypatch.setenv("ADMIN_PASSWORD", "env-admin")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    app = create_app()

    assert app.config["SECRET_KEY"] == "env-secret"
    assert app.config["ADMIN_PASSWORD"] == "env-admin"
    assert app.config["DATABASE_URL"].startswith("postgresql://")


def test_create_app_requires_secret_key():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY is required"):
            create_app(
                {
                    "ADMIN_PASSWORD": "test-admin-password",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/postgres",
                }
            )


def test_create_app_requires_admin_password():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="ADMIN_PASSWORD is required"):
            create_app(
                {
                    "SECRET_KEY": "test-secret-key",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/postgres",
                }
            )


def test_create_app_requires_database_url():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
            create_app(
                {
                    "SECRET_KEY": "test-secret-key",
                    "ADMIN_PASSWORD": "test-admin-password",
                }
            )


def test_csrf_protection_blocks_post_without_token(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "env-secret")
    monkeypatch.setenv("ADMIN_PASSWORD", "env-admin")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    app = create_app()
    client = app.test_client()

    response = client.post("/admin/login", data={"password": "env-admin"})

    assert response.status_code == 400
