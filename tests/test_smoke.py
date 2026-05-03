def test_app_factory_creates_app(app):
    assert app.name == "app"
    assert app.testing is True


def test_homepage_shows_featured_listing(client, monkeypatch, fake_db):
    monkeypatch.setattr("app.routes.listings.get_db", lambda: fake_db)

    response = client.get("/")

    assert response.status_code == 200
    assert b"Central Studios" in response.data
    assert b"Student Housing Made Simple" in response.data


def test_listings_page_renders_filters_and_results(client, monkeypatch, fake_db):
    monkeypatch.setattr("app.routes.listings.get_db", lambda: fake_db)

    response = client.get("/listings?city=Leeds&sort=price_asc")

    assert response.status_code == 200
    assert b"All Listings" in response.data
    assert b"Central Studios" in response.data
    assert any("city = %s" in query for query, _ in fake_db.calls)
    assert any("ORDER BY rent_pcm ASC, created DESC" in query for query, _ in fake_db.calls)


def test_admin_login_success_redirects_to_dashboard(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth.sign_in_with_supabase",
        lambda email, password: {
            "access_token": "token-123",
            "user": {
                "id": "user-123",
                "email": email,
            },
        },
    )
    monkeypatch.setattr(
        "app.routes.auth.load_profile",
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
        "app.routes.auth.verify_confirmation_token",
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
        "app.routes.auth.verify_confirmation_token",
        lambda token_hash, otp_type: (_ for _ in ()).throw(RuntimeError("Confirmation link is invalid or expired.")),
    )

    response = client.get("/auth/confirm?token_hash=test-token&type=email", follow_redirects=False)

    assert response.status_code == 302
    assert "/account?mode=login" in response.headers["Location"]


def test_register_without_immediate_user_record_redirects_to_login(client, monkeypatch):
    monkeypatch.setattr("app.routes.auth.verify_protected_form", lambda *_args, **_kwargs: (True, None))
    monkeypatch.setattr(
        "app.routes.auth.sign_up_with_supabase",
        lambda email, password, email_redirect_to, display_name=None: {
            "access_token": None,
            "user": None,
        },
    )

    response = client.post(
        "/account",
        data={
            "mode": "register",
            "display_name": "New Landlord",
            "email": "new@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"If this email is new, check your inbox to confirm it." in response.data
    assert b"Account created." not in response.data


def test_register_existing_account_redirects_to_login_with_info(client, monkeypatch):
    monkeypatch.setattr("app.routes.auth.verify_protected_form", lambda *_args, **_kwargs: (True, None))
    monkeypatch.setattr(
        "app.routes.auth.sign_up_with_supabase",
        lambda email, password, email_redirect_to, display_name=None: {
            "existing_account": True,
            "user": {"id": "existing-user", "identities": []},
        },
    )

    response = client.post(
        "/account",
        data={
            "mode": "register",
            "display_name": "Existing Landlord",
            "email": "existing@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please log in instead." in response.data
    assert b"Account created." not in response.data
