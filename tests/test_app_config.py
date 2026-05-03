import pytest

from app import create_app


def test_create_app_uses_instance_config_when_no_test_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "env-secret")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "env-publishable-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    app = create_app()

    assert app.config["SECRET_KEY"] == "env-secret"
    assert app.config["SUPABASE_URL"] == "https://example.supabase.co"
    assert app.config["SUPABASE_PUBLISHABLE_KEY"] == "env-publishable-key"
    assert app.config["DATABASE_URL"].startswith("postgresql://")


def test_create_app_requires_secret_key():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY is required"):
            create_app(
                {
                    "SECRET_KEY": "",
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_PUBLISHABLE_KEY": "test-publishable-key",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/postgres",
                }
            )


def test_create_app_requires_supabase_auth_config():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required"):
            create_app(
                {
                    "SECRET_KEY": "test-secret-key",
                    "SUPABASE_URL": "",
                    "SUPABASE_PUBLISHABLE_KEY": "",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/postgres",
                }
            )


def test_create_app_requires_database_url():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
            create_app(
                {
                    "SECRET_KEY": "test-secret-key",
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_PUBLISHABLE_KEY": "test-publishable-key",
                    "DATABASE_URL": "",
                }
            )


def test_csrf_protection_blocks_post_without_token(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "env-secret")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "env-publishable-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    app = create_app()
    client = app.test_client()

    response = client.post("/account", data={"email": "admin@example.com", "password": "secret"})

    assert response.status_code == 400
