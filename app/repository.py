import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus
from app.schemas import BookingCreate


async def create_booking(session: AsyncSession, data: BookingCreate) -> Booking:
    booking = Booking(
        name=data.name,
        scheduled_at=data.scheduled_at,
        service_type=data.service_type,
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


async def get_booking(session: AsyncSession, booking_id: uuid.UUID) -> Booking | None:
    return await session.get(Booking, booking_id)


async def list_bookings(
    session: AsyncSession,
    status: BookingStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Booking], int]:
    filters = [Booking.status == status] if status is not None else []

    total = await session.scalar(select(func.count()).select_from(Booking).where(*filters))
    rows = await session.scalars(
        select(Booking)
        .where(*filters)
        .order_by(Booking.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def transition_status(
    session: AsyncSession,
    booking_id: uuid.UUID,
    new_status: BookingStatus,
) -> bool:
    result = await session.execute(
        update(Booking)
        .where(Booking.id == booking_id, Booking.status == BookingStatus.pending)
        .values(status=new_status)
    )
    await session.commit()
    return result.rowcount > 0
