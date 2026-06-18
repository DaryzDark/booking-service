import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import Context, TaskiqDepends

from app.config import settings
from app.database import get_session
from app.logging import get_logger
from app.models import BookingStatus
from app.repository import transition_status
from app.tasks.broker import broker

logger = get_logger("worker")


class ExternalServiceError(RuntimeError):
    """Simulated error from the external service."""


async def call_external_service(booking_id: uuid.UUID) -> None:
    if random.random() < settings.failure_rate:
        raise ExternalServiceError(f"external service rejected booking {booking_id}")


async def send_mock_notification(booking_id: uuid.UUID) -> None:
    logger.info("notification_sent", booking_id=str(booking_id), channel="mock")


async def confirm_booking_logic(
    session: AsyncSession,
    booking_id: uuid.UUID,
    retries: int,
    max_retries: int,
) -> None:
    log = logger.bind(booking_id=str(booking_id), attempt=retries + 1)
    try:
        await call_external_service(booking_id)
    except ExternalServiceError as exc:
        is_last_attempt = retries >= max_retries - 1
        if is_last_attempt:
            if await transition_status(session, booking_id, BookingStatus.failed):
                log.warning("booking_failed", reason=str(exc))
            else:
                log.info("booking_skipped_not_pending")
            return
        log.warning("booking_attempt_failed", reason=str(exc))
        raise

    if await transition_status(session, booking_id, BookingStatus.confirmed):
        log.info("booking_confirmed")
        await send_mock_notification(booking_id)
    else:
        log.info("booking_skipped_not_pending")


@broker.task(retry_on_error=True)
async def confirm_booking(
    booking_id: str,
    context: Context = TaskiqDepends(),
    session: AsyncSession = TaskiqDepends(get_session),
) -> None:
    retries = int(context.message.labels.get("_retries", 0))
    await confirm_booking_logic(session, uuid.UUID(booking_id), retries, settings.max_retries)
