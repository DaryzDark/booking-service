import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.models import Booking, BookingStatus
from app.rate_limit import limiter


def _future(days: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def test_create_booking_happy_path(client, enqueue_mock, booking_payload):
    resp = await client.post("/bookings", json=booking_payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["name"] == "Ann Smith"
    assert body["service_type"] == "haircut"
    assert "datetime" in body
    uuid.UUID(body["id"]) 
    enqueue_mock.assert_awaited_once_with(body["id"])


@pytest.mark.parametrize(
    "payload",
    [
        {"datetime": _future(), "service_type": "haircut"},  # missing name
        {"name": "   ", "datetime": _future(), "service_type": "haircut"},  # blank name
        {"name": "Ann", "datetime": _future(), "service_type": ""},  # empty service_type
        {"name": "Ann", "datetime": "2000-01-01T00:00:00+00:00", "service_type": "x"},  # past
        {"name": "Ann", "datetime": "not-a-date", "service_type": "x"},  # unparseable
    ],
)
async def test_create_booking_validation_errors(client, payload):
    resp = await client.post("/bookings", json=payload)
    assert resp.status_code == 422


async def test_get_booking(client, booking_payload):
    created = (await client.post("/bookings", json=booking_payload)).json()

    resp = await client.get(f"/bookings/{created['id']}")

    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_booking_not_found(client):
    resp = await client.get(f"/bookings/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_booking_invalid_uuid(client):
    resp = await client.get("/bookings/not-a-uuid")
    assert resp.status_code == 422


async def test_list_filter_and_pagination(client, booking_payload):
    for i in range(3):
        await client.post("/bookings", json={**booking_payload, "name": f"User {i}"})

    all_pending = (await client.get("/bookings", params={"status": "pending"})).json()
    assert all_pending["total"] == 3
    assert len(all_pending["items"]) == 3

    page1 = (await client.get("/bookings", params={"limit": 2, "offset": 0})).json()
    page2 = (await client.get("/bookings", params={"limit": 2, "offset": 2})).json()
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    assert page1["total"] == 3

    confirmed = (await client.get("/bookings", params={"status": "confirmed"})).json()
    assert confirmed["total"] == 0
    assert confirmed["items"] == []


async def test_cancel_pending_booking(client, booking_payload):
    created = (await client.post("/bookings", json=booking_payload)).json()

    resp = await client.delete(f"/bookings/{created['id']}")
    assert resp.status_code == 204

    got = await client.get(f"/bookings/{created['id']}")
    assert got.json()["status"] == "cancelled"


async def test_cancel_non_pending_returns_409(client, session, booking_payload):
    created = (await client.post("/bookings", json=booking_payload)).json()
    booking = await session.get(Booking, uuid.UUID(created["id"]))
    booking.status = BookingStatus.confirmed
    await session.commit()

    resp = await client.delete(f"/bookings/{created['id']}")
    assert resp.status_code == 409


async def test_cancel_not_found(client):
    resp = await client.delete(f"/bookings/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_rate_limit_on_post(client, booking_payload, monkeypatch):
    limiter.enabled = True
    limiter.reset()
    monkeypatch.setattr(settings, "rate_limit", "3/minute")

    for _ in range(3):
        ok = await client.post("/bookings", json=booking_payload)
        assert ok.status_code == 201

    blocked = await client.post("/bookings", json=booking_payload)
    assert blocked.status_code == 429
