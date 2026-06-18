"""create bookings table

Revision ID: 0001_create_bookings
Revises:
Create Date: 2026-06-17

"""

import sqlalchemy as sa

from alembic import op

revision = "0001_create_bookings"
down_revision = None
branch_labels = None
depends_on = None

booking_status = sa.Enum(
    "pending",
    "confirmed",
    "failed",
    "cancelled",
    name="bookingstatus",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_type", sa.String(length=100), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bookings_status"), table_name="bookings")
    op.drop_table("bookings")
