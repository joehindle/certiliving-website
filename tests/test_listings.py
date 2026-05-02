from types import SimpleNamespace
import json

import pytest

from app import listings


class DetailFakeDB:
    def __init__(self, listing, similar_listings=None, fallback_listings=None):
        self.listing = listing
        self.similar_listings = similar_listings or []
        self.fallback_listings = fallback_listings or []
        self.calls = []
        self.enquiries = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        normalized_query = query.strip()

        if normalized_query.startswith("SELECT * FROM listings WHERE id = %s"):
            return SimpleNamespace(fetchone=lambda: self.listing)

        if "ORDER BY ABS(rent_pcm - %s) ASC" in normalized_query:
            return SimpleNamespace(fetchall=lambda: self.similar_listings)

        if "WHERE id NOT IN" in normalized_query:
            return SimpleNamespace(fetchall=lambda: self.fallback_listings)

        if normalized_query.startswith("INSERT INTO enquiries"):
            self.enquiries.append((query, params))
            return SimpleNamespace(fetchall=lambda: [])

        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)

    def commit(self):
        return None


@pytest.mark.parametrize(
    "name,email,message,expected",
    [
        ("", "test@example.com", "hello", "Name is required."),
        ("Name", "", "hello", "Email is required."),
        ("Name", "test@example.com", "", "Message is required."),
        ("a" * 101, "test@example.com", "hello", "Name is too long."),
        ("Name", "bad-email", "hello", "Invalid email address."),
        ("Name", "test@example.com", "a" * 1501, "Message is too long."),
    ],
)
def test_validate_enquiry_form_rejects_invalid_inputs(name, email, message, expected):
    assert listings._validate_enquiry_form(name, email, message) == expected


def test_validate_enquiry_form_accepts_valid_input():
    assert listings._validate_enquiry_form("Name", "test@example.com", "Hello") is None


def test_listing_description_paragraphs_splits_blank_lines():
    paragraphs = listings._listing_description_paragraphs(
        "First paragraph.\n\nSecond paragraph.\r\n\r\nThird paragraph."
    )

    assert paragraphs == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]


def test_listing_image_urls_prefers_cover_then_supporting_photos():
    listing = {
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [
            "https://cdn.example.com/listings/support-1.webp",
            "https://cdn.example.com/listings/support-2.webp",
        ],
    }

    assert listings._listing_image_urls(listing) == [
        "https://cdn.example.com/listings/cover.webp",
        "https://cdn.example.com/listings/support-1.webp",
        "https://cdn.example.com/listings/support-2.webp",
    ]


def test_verify_turnstile_token_accepts_valid_response(app, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"success": True}).encode("utf-8")

    monkeypatch.setattr("app.listings.urlopen", lambda *_args, **_kwargs: FakeResponse())

    with app.test_request_context("/"):
        app.config.update(
            TURNSTILE_SITE_KEY="site-key",
            TURNSTILE_SECRET_KEY="secret-key",
        )
        ok, errors = listings._verify_turnstile_token("token-value", "127.0.0.1")

    assert ok is True
    assert errors == []


def test_verify_turnstile_token_rejects_missing_token(app):
    with app.test_request_context("/"):
        app.config.update(
            TURNSTILE_SITE_KEY="site-key",
            TURNSTILE_SECRET_KEY="secret-key",
        )
        ok, errors = listings._verify_turnstile_token("", "127.0.0.1")

    assert ok is False
    assert errors == ["missing-input-response"]


def test_detail_route_returns_404_when_listing_missing(client, monkeypatch):
    fake_db = DetailFakeDB(None)
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.get("/listings/999")

    assert response.status_code == 404


def test_detail_route_saves_enquiry_and_redirects(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [],
    }
    fake_db = DetailFakeDB(listing, similar_listings=[], fallback_listings=[])
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)
    monkeypatch.setattr("app.listings._send_enquiry_email", lambda *args, **kwargs: None)

    response = client.post(
        "/listings/1",
        data={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "I am interested in this property.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert fake_db.enquiries


def test_detail_route_renders_description_as_paragraphs(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "description": "First paragraph.\n\nSecond paragraph.",
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [],
    }
    fake_db = DetailFakeDB(listing, similar_listings=[], fallback_listings=[])
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.get("/listings/1")

    assert response.status_code == 200
    assert b"<p class=\"detail-desc\">First paragraph.</p>" in response.data
    assert b"<p class=\"detail-desc\">Second paragraph.</p>" in response.data


def test_detail_route_blocks_honeypot_submission(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [],
    }
    fake_db = DetailFakeDB(listing, similar_listings=[], fallback_listings=[])
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.post(
        "/listings/1",
        data={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "I am interested in this property.",
            "website": "spammy-site.example",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert not fake_db.enquiries


def test_detail_route_rejects_invalid_enquiry(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [],
    }
    fake_db = DetailFakeDB(listing)
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.post(
        "/listings/1",
        data={
            "name": "",
            "email": "alice@example.com",
            "message": "I am interested in this property.",
        },
    )

    assert response.status_code == 200
    assert not fake_db.enquiries


def test_detail_route_handles_email_failure(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "photo_url": "https://cdn.example.com/listings/cover.webp",
        "supporting_photo_urls": [],
    }
    fake_db = DetailFakeDB(listing, similar_listings=[], fallback_listings=[])
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)
    monkeypatch.setattr("app.listings._send_enquiry_email", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("boom")))

    response = client.post(
        "/listings/1",
        data={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "I am interested in this property.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert fake_db.enquiries


def test_all_listings_handles_invalid_filters_and_pagination(client, monkeypatch, fake_db):
    monkeypatch.setattr("app.listings.get_db", lambda: fake_db)

    response = client.get(
        "/listings?city=Leeds&room_type=Studio&bills_only=1&min_rent=abc&max_rent=xyz&sort=unexpected&page=999&per_page=5"
    )

    assert response.status_code == 200
    assert any("city = %s" in query for query, _ in fake_db.calls)
    assert any("room_type = %s" in query for query, _ in fake_db.calls)
    assert any("bills_included = TRUE" in query for query, _ in fake_db.calls)
    assert any("ORDER BY created DESC" in query for query, _ in fake_db.calls)


def test_send_enquiry_email_builds_payload(app, monkeypatch):
    listing = {"id": 1, "title": "Central & Studios", "city": "Leeds"}
    captured = {}

    def fake_send(payload):
        captured["payload"] = payload

    monkeypatch.setattr("app.listings.resend.Emails.send", fake_send)

    with app.test_request_context("/"):
        app.config.update(
            RESEND_API_KEY="test-resend-key",
            ENQUIRY_TO_EMAIL="team@example.com",
            RESEND_FROM_EMAIL="onboarding@example.com",
        )
        listings._send_enquiry_email(listing, "Alice <Admin>", "alice@example.com", "Hello\nWorld")

    assert captured["payload"]["from"] == "onboarding@example.com"
    assert captured["payload"]["to"] == "team@example.com"
    assert "Alice &lt;Admin&gt;" in captured["payload"]["html"]
    assert "Hello<br>World" in captured["payload"]["html"]


@pytest.mark.parametrize(
    "config_updates, expected_message",
    [
        (
            {
                "RESEND_API_KEY": "",
                "ENQUIRY_TO_EMAIL": "team@example.com",
                "RESEND_FROM_EMAIL": "onboarding@example.com",
            },
            "Missing RESEND_API_KEY",
        ),
        (
            {
                "RESEND_API_KEY": "test-resend-key",
                "ENQUIRY_TO_EMAIL": "",
                "RESEND_FROM_EMAIL": "onboarding@example.com",
            },
            "Missing ENQUIRY_TO_EMAIL",
        ),
        (
            {
                "RESEND_API_KEY": "test-resend-key",
                "ENQUIRY_TO_EMAIL": "team@example.com",
                "RESEND_FROM_EMAIL": "",
            },
            "Missing RESEND_FROM_EMAIL",
        ),
    ],
)
def test_send_enquiry_email_requires_config(app, config_updates, expected_message):
    listing = {"id": 1, "title": "Central Studios", "city": "Leeds"}

    with app.test_request_context("/"):
        app.config.update(config_updates)

        with pytest.raises(RuntimeError, match=expected_message):
            listings._send_enquiry_email(listing, "Alice", "alice@example.com", "Hello")
