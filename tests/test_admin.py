from io import BytesIO
from types import SimpleNamespace

from werkzeug.datastructures import MultiDict

from app import admin


class AdminFakeDB:
    def __init__(self, listings=None, listing=None, photo_url="https://cdn.example.com/listings/old.webp"):
        self.listings = listings or []
        self.listing = listing
        self.photo_url = photo_url
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))

        if query.startswith("SELECT * FROM listings ORDER BY created DESC"):
            return SimpleNamespace(fetchall=lambda: self.listings)

        if query.startswith("SELECT * FROM listings WHERE id = %s"):
            return SimpleNamespace(fetchone=lambda: self.listing)

        if query.startswith("SELECT photo_url, supporting_photo_urls FROM listings WHERE id = %s"):
            return SimpleNamespace(
                fetchone=lambda: {
                    "photo_url": self.photo_url,
                    "supporting_photo_urls": (self.listing or {}).get("supporting_photo_urls", []),
                } if self.listing else None
            )

        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: self.listing)

    def commit(self):
        return None


def _login_as_admin(client):
    with client.session_transaction() as session:
        session["is_admin"] = True


def test_clean_optional_and_listing_parsers():
    assert admin._clean_optional("  Leeds  ") == "Leeds"
    assert admin._clean_optional("   ") is None

    form = {
        "title": "  Central Studios ",
        "city": " Leeds ",
        "rent_pcm": "650",
        "room_type": " Studio ",
        "bills_included": "on",
        "available_from": " 2026-09-01 ",
        "description": " Modern studio. ",
    }
    parsed = admin._parse_listing_form(form)
    assert parsed["title"] == "Central Studios"
    assert parsed["city"] == "Leeds"
    assert parsed["room_type"] == "Studio"
    assert parsed["bills_included"] is True
    assert parsed["available_from"] == "2026-09-01"
    assert parsed["description"] == "Modern studio."

    preview = admin._listing_preview_from_form(
        form,
        existing_photo_url="https://example.com/photo.webp",
        existing_supporting_photo_urls=["https://example.com/support-1.webp"],
    )
    assert preview["photo_url"] == "https://example.com/photo.webp"
    assert preview["supporting_photo_urls"] == ["https://example.com/support-1.webp"]
    assert preview["title"] == "Central Studios"


def test_admin_home_redirects_to_listings(client):
    _login_as_admin(client)

    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/listings" in response.headers["Location"]


def test_admin_listings_index_renders_listings(client, monkeypatch, sample_listings):
    _login_as_admin(client)
    fake_db = AdminFakeDB(listings=sample_listings)
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)

    response = client.get("/admin/listings")

    assert response.status_code == 200
    assert b"Central Studios" in response.data


def test_admin_login_failure_shows_message(client, monkeypatch):
    monkeypatch.setattr("app.admin.time.sleep", lambda *_args, **_kwargs: None)

    response = client.post(
        "/admin/login",
        data={"password": "wrong-password"},
    )

    assert response.status_code == 200
    assert b"Wrong password." in response.data


def test_admin_listings_new_posts_listing(client, monkeypatch):
    _login_as_admin(client)
    fake_db = AdminFakeDB()
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)
    monkeypatch.setattr("app.admin._upload_listing_image", lambda _photo: "https://cdn.example.com/listings/new.webp")
    monkeypatch.setattr(
        "app.admin._upload_listing_images",
        lambda _photos: ["https://cdn.example.com/listings/support-1.webp"],
    )

    response = client.post(
        "/admin/listings/new",
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
    assert any(query.startswith("INSERT INTO listings") for query, _ in fake_db.calls)


def test_admin_listings_new_handles_upload_failure(client, monkeypatch):
    _login_as_admin(client)
    fake_db = AdminFakeDB()
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)
    monkeypatch.setattr("app.admin._upload_listing_image", lambda _photo: (_ for _ in ()).throw(ValueError("bad image")))

    response = client.post(
        "/admin/listings/new",
        data={
            "title": "New Listing",
            "city": "Leeds",
            "rent_pcm": "725",
            "description": "Fresh listing",
            "cover_photo_file": (BytesIO(b"not-an-image"), "listing.txt"),
        },
    )

    assert response.status_code == 200
    assert b"Image upload failed" in response.data


def test_admin_listings_new_requires_cover_photo(client, monkeypatch):
    _login_as_admin(client)
    fake_db = AdminFakeDB()
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)

    response = client.post(
        "/admin/listings/new",
        data={
            "title": "New Listing",
            "city": "Leeds",
            "rent_pcm": "725",
            "description": "Fresh listing",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Cover photo is required." in response.data
    assert not any(query.startswith("INSERT INTO listings") for query, _ in fake_db.calls)


def test_admin_listings_edit_updates_listing(client, monkeypatch):
    _login_as_admin(client)
    existing = {
        "id": 1,
        "title": "Central Studios",
        "city": "Leeds",
        "rent_pcm": 650,
        "photo_url": "https://cdn.example.com/listings/old.webp",
        "supporting_photo_urls": ["https://cdn.example.com/listings/support-old.webp"],
        "room_type": "Studio",
        "bills_included": True,
        "available_from": "2026-09-01",
        "description": "Modern studio flat.",
    }
    fake_db = AdminFakeDB(listing=existing)
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)
    monkeypatch.setattr("app.admin._upload_listing_image", lambda _photo: "https://cdn.example.com/listings/new.webp")
    deleted = []
    monkeypatch.setattr("app.admin._delete_r2_image", lambda photo_url: deleted.append(photo_url))

    response = client.post(
        "/admin/listings/1/edit",
        data={
            "title": "Updated Listing",
            "city": "Leeds",
            "rent_pcm": "700",
            "room_type": "Studio",
            "description": "Updated description",
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert deleted == []
    assert any(query.startswith("UPDATE listings") for query, _ in fake_db.calls)


def test_admin_listings_delete_removes_listing(client, monkeypatch):
    _login_as_admin(client)
    fake_db = AdminFakeDB(
        listing={
            "photo_url": "https://cdn.example.com/listings/old.webp",
            "supporting_photo_urls": ["https://cdn.example.com/listings/support-old.webp"],
        }
    )
    monkeypatch.setattr("app.admin.get_db", lambda: fake_db)
    deleted = []
    monkeypatch.setattr("app.admin._delete_r2_image", lambda photo_url: deleted.append(photo_url))
    monkeypatch.setattr("app.admin._delete_r2_images", lambda photo_urls: deleted.extend(photo_urls))

    response = client.post("/admin/listings/1/delete", follow_redirects=False)

    assert response.status_code == 302
    assert deleted == [
        "https://cdn.example.com/listings/old.webp",
        "https://cdn.example.com/listings/support-old.webp",
    ]
    assert any(query.startswith("DELETE FROM listings") for query, _ in fake_db.calls)
