from types import SimpleNamespace

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


def test_detail_route_rejects_invalid_enquiry(client, monkeypatch):
    listing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
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
