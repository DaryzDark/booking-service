from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models import Booking, BookingStatus
from app.tasks import confirm as confirm_module
from app.tasks.confirm import ExternalServiceError, confirm_booking_logic


async def _make_booking(session, status: BookingStatus = BookingStatus.pending) -> Booking:
    booking = Booking(
        name="Worker Test",
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        service_type="haircut",
        status=status,
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


@pytest.fixture
def no_external_failure(monkeypatch):
    monkeypatch.setattr(confirm_module, "call_external_service", AsyncMock())


@pytest.fixture
def always_external_failure(monkeypatch):
    monkeypatch.setattr(
        confirm_module,
        "call_external_service",
        AsyncMock(side_effect=ExternalServiceError("external down")),
    )


@pytest.fixture
def notification_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(confirm_module, "send_mock_notification", spy)
    return spy


async def test_confirm_success(session, no_external_failure, notification_spy):
    booking = await _make_booking(session)

    await confirm_booking_logic(session, booking.id, retries=0, max_retries=3)

    await session.refresh(booking)
    assert booking.status == BookingStatus.confirmed
    notification_spy.assert_awaited_once_with(booking.id)


async def test_confirm_marks_failed_on_last_attempt(session, always_external_failure):
    booking = await _make_booking(session)

    await confirm_booking_logic(session, booking.id, retries=2, max_retries=3)

    await session.refresh(booking)
    assert booking.status == BookingStatus.failed


async def test_confirm_reraises_for_retry(session, always_external_failure):
    booking = await _make_booking(session)

    with pytest.raises(ExternalServiceError):
        await confirm_booking_logic(session, booking.id, retries=0, max_retries=3)

    await session.refresh(booking)
    assert booking.status == BookingStatus.pending 


async def test_confirm_is_idempotent(session, no_external_failure, notification_spy):
    booking = await _make_booking(session)

    await confirm_booking_logic(session, booking.id, 0, 3)
    await confirm_booking_logic(session, booking.id, 0, 3)  

    await session.refresh(booking)
    assert booking.status == BookingStatus.confirmed
    notification_spy.assert_awaited_once()  


async def test_confirm_skips_cancelled_booking(session, no_external_failure, notification_spy):
    booking = await _make_booking(session, status=BookingStatus.cancelled)

    await confirm_booking_logic(session, booking.id, 0, 3)

    await session.refresh(booking)
    assert booking.status == BookingStatus.cancelled  
    notification_spy.assert_not_awaited()
