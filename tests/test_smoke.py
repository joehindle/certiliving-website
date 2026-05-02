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
            "id": "user-123",
            "email": email,
            "app_metadata": {"role": "admin"},
        },
    )

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "test-password"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/listings" in response.headers["Location"]


def test_admin_area_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
