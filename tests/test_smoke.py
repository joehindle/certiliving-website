def test_app_factory_creates_app(app):
    assert app.name == "app"
    assert app.testing is True


def test_homepage_shows_featured_listing(client, monkeypatch, fake_db):
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.get("/")

    assert response.status_code == 200
    assert b"Central Studios" in response.data
    assert b"Student Housing Made Simple" in response.data


def test_listings_page_renders_filters_and_results(client, monkeypatch, fake_db):
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.get("/listings?city=Leeds&sort=price_asc")

    assert response.status_code == 200
    assert b"All Listings" in response.data
    assert b"Central Studios" in response.data
    assert any("city = %s" in query for query, _ in fake_db.calls)
    assert any("ORDER BY rent_pcm ASC, created DESC" in query for query, _ in fake_db.calls)


def test_admin_login_success_redirects_to_dashboard(client, monkeypatch):
    monkeypatch.setattr(
        "app.auth._sign_in_with_supabase",
        lambda email, password: {
            "access_token": "token-123",
            "user": {
                "id": "user-123",
                "email": email,
            },
        },
    )
    monkeypatch.setattr(
        "app.auth._load_profile",
        lambda access_token, user_id: {
            "id": user_id,
            "email": "admin@example.com",
            "role": "admin",
        },
    )

    response = client.post(
        "/account",
        data={"email": "admin@example.com", "password": "test-password"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/listings" in response.headers["Location"]


def test_admin_area_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert "/account" in response.headers["Location"]


def test_auth_confirm_redirects_to_verified_login(client, monkeypatch):
    monkeypatch.setattr(
        "app.auth._verify_confirmation_token",
        lambda token_hash, otp_type: {
            "user": {"id": "user-123"},
            "session": None,
        },
    )

    response = client.get("/auth/confirm?token_hash=test-token&type=email", follow_redirects=False)

    assert response.status_code == 302
    assert "/account?mode=login&verified=1" in response.headers["Location"]


def test_auth_confirm_handles_invalid_token(client, monkeypatch):
    monkeypatch.setattr(
        "app.auth._verify_confirmation_token",
        lambda token_hash, otp_type: (_ for _ in ()).throw(RuntimeError("Confirmation link is invalid or expired.")),
    )

    response = client.get("/auth/confirm?token_hash=test-token&type=email", follow_redirects=False)

    assert response.status_code == 302
    assert "/account?mode=login" in response.headers["Location"]
