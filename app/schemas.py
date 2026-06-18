import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import BookingStatus


class BookingCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    scheduled_at: datetime = Field(alias="datetime")
    service_type: str = Field(min_length=1, max_length=255)

    @field_validator("name", "service_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def _must_be_future(cls, value: datetime) -> datetime:
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        if moment <= datetime.now(UTC):
            raise ValueError("datetime must be in the future")
        return value


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    scheduled_at: datetime = Field(serialization_alias="datetime")
    service_type: str
    status: BookingStatus
    created_at: datetime


class BookingList(BaseModel):
    items: list[BookingRead]
    total: int
    limit: int
    offset: int
