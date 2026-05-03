from io import BytesIO
from types import SimpleNamespace

from werkzeug.datastructures import MultiDict


class LandlordFakeDB:
    def __init__(self, listings=None, listing=None, photo_url="https://cdn.example.com/listings/old.webp"):
        self.listings = listings or []
        self.listing = listing
        self.photo_url = photo_url
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))

        if query.startswith("SELECT * FROM listings WHERE owner_id = %s ORDER BY created DESC"):
            return SimpleNamespace(fetchall=lambda: self.listings)

        if query.startswith("SELECT * FROM listings WHERE id = %s AND owner_id = %s"):
            return SimpleNamespace(fetchone=lambda: self.listing)

        if query.startswith("SELECT photo_url, supporting_photo_urls FROM listings WHERE id = %s AND owner_id = %s"):
            return SimpleNamespace(
                fetchone=lambda: {
                    "photo_url": self.photo_url,
                    "supporting_photo_urls": (self.listing or {}).get("supporting_photo_urls", []),
                } if self.listing else None
            )

        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: self.listing)

    def commit(self):
        return None


def _login_as_landlord(client):
    with client.session_transaction() as session:
        session["auth_user_id"] = "landlord-123"
        session["auth_email"] = "landlord@example.com"
        session["auth_roles"] = ["landlord"]


def test_landlord_dashboard_requires_login(client):
    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 302
    assert "/account" in response.headers["Location"]


def test_landlord_dashboard_renders_owned_listings(client, monkeypatch, sample_listings):
    _login_as_landlord(client)
    fake_db = LandlordFakeDB(listings=sample_listings)
    monkeypatch.setattr("app.landlord.get_db", lambda: fake_db)

    response = client.get("/dashboard/listings")

    assert response.status_code == 200
    assert b"Your listings" in response.data
    assert b"Central Studios" in response.data
    assert any("WHERE owner_id = %s" in query for query, _ in fake_db.calls)


def test_landlord_create_listing_sets_owner_id(client, monkeypatch):
    _login_as_landlord(client)
    fake_db = LandlordFakeDB()
    monkeypatch.setattr("app.landlord.get_db", lambda: fake_db)
    monkeypatch.setattr("app.landlord._process_listing_images", lambda **_kwargs: (
        "https://cdn.example.com/listings/new.webp",
        ["https://cdn.example.com/listings/support-1.webp"],
    ))

    response = client.post(
        "/dashboard/listings/new",
        data=MultiDict([
            ("title", "New Listing"),
            ("city", "Leeds"),
            ("rent_pcm", "725"),
            ("room_type", "Studio"),
            ("description", "Fresh listing"),
            ("cover_photo_file", (BytesIO(b"cover"), "cover.webp")),
            ("supporting_photo_files", (BytesIO(b"support"), "support.webp")),
        ]),
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    insert_calls = [
        params for query, params in fake_db.calls
        if query.startswith("INSERT INTO listings")
    ]
    assert insert_calls
    assert insert_calls[0][-1] == "landlord-123"


def test_landlord_cannot_edit_other_users_listing(client, monkeypatch):
    _login_as_landlord(client)
    fake_db = LandlordFakeDB(listing=None)
    monkeypatch.setattr("app.landlord.get_db", lambda: fake_db)

    response = client.get("/dashboard/listings/1/edit")

    assert response.status_code == 404


def test_landlord_delete_only_owned_listing(client, monkeypatch):
    _login_as_landlord(client)
    fake_db = LandlordFakeDB(
        listing={
            "photo_url": "https://cdn.example.com/listings/old.webp",
            "supporting_photo_urls": ["https://cdn.example.com/listings/support-old.webp"],
        }
    )
    monkeypatch.setattr("app.landlord.get_db", lambda: fake_db)
    deleted = []
    monkeypatch.setattr("app.landlord._delete_r2_image", lambda photo_url: deleted.append(photo_url))
    monkeypatch.setattr("app.landlord._delete_r2_images", lambda photo_urls: deleted.extend(photo_urls))

    response = client.post("/dashboard/listings/1/delete", follow_redirects=False)

    assert response.status_code == 302
    assert deleted == [
        "https://cdn.example.com/listings/old.webp",
        "https://cdn.example.com/listings/support-old.webp",
    ]
    assert any("DELETE FROM listings WHERE id = %s AND owner_id = %s" in query for query, _ in fake_db.calls)
