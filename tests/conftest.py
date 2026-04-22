import pytest

from app import create_app


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    def __init__(self, listings):
        self.listings = listings
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))

        if query.startswith("SELECT COUNT(*) AS total FROM listings"):
            return FakeResult([{"total": len(self.listings)}])

        if query.startswith("SELECT DISTINCT city FROM listings"):
            cities = sorted(
                {
                    row["city"]
                    for row in self.listings
                    if row.get("city")
                }
            )
            return FakeResult([{"city": city} for city in cities])

        if query.startswith("SELECT DISTINCT room_type FROM listings"):
            room_types = sorted(
                {
                    row["room_type"]
                    for row in self.listings
                    if row.get("room_type")
                }
            )
            return FakeResult([{"room_type": room_type} for room_type in room_types])

        if query.startswith("SELECT * FROM listings"):
            return FakeResult(self.listings)

        if query.startswith("INSERT INTO listings"):
            return FakeResult([])

        if query.startswith("UPDATE listings"):
            return FakeResult([])

        if query.startswith("DELETE FROM listings"):
            return FakeResult([])

        return FakeResult([])

    def commit(self):
        return None


@pytest.fixture
def sample_listings():
    return [
        {
            "id": 1,
            "title": "Central Studios",
            "city": "Leeds",
            "rent_pcm": 650,
            "photo_url": None,
            "room_type": "Studio",
            "bills_included": True,
            "available_from": "2026-09-01",
            "description": "Modern studio flat.",
            "created": "2026-04-22 10:00:00",
        },
        {
            "id": 2,
            "title": "River House",
            "city": "Manchester",
            "rent_pcm": 700,
            "photo_url": None,
            "room_type": "Ensuite",
            "bills_included": False,
            "available_from": None,
            "description": "Bright room near campus.",
            "created": "2026-04-21 10:00:00",
        },
    ]


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "ADMIN_PASSWORD": "test-admin-password",
            "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/postgres",
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_db(sample_listings):
    return FakeDB(sample_listings)
