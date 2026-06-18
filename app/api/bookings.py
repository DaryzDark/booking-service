import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.logging import get_logger
from app.models import BookingStatus
from app.rate_limit import limiter, rate_limit_value
from app.repository import (
    create_booking,
    get_booking,
    list_bookings,
    transition_status,
)
from app.schemas import BookingCreate, BookingList, BookingRead
from app.tasks.confirm import confirm_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])

logger = get_logger("api")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_value)
async def create(request: Request, payload: BookingCreate, session: SessionDep) -> BookingRead:
    booking = await create_booking(session, payload)
    await confirm_booking.kiq(str(booking.id))
    logger.info("booking_created", booking_id=str(booking.id), service_type=booking.service_type)
    return BookingRead.model_validate(booking)


@router.get("/{booking_id}", response_model=BookingRead)
async def retrieve(booking_id: uuid.UUID, session: SessionDep) -> BookingRead:
    booking = await get_booking(session, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return BookingRead.model_validate(booking)


@router.get("", response_model=BookingList)
async def list_(
    session: SessionDep,
    status_filter: Annotated[BookingStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BookingList:
    items, total = await list_bookings(session, status_filter, limit, offset)
    return BookingList(
        items=[BookingRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel(booking_id: uuid.UUID, session: SessionDep) -> Response:
    booking = await get_booking(session, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != BookingStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending bookings can be cancelled",
        )
    if not await transition_status(session, booking_id, BookingStatus.cancelled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending bookings can be cancelled",
        )
    logger.info("booking_cancelled", booking_id=str(booking_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
