from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.rate_limit import limiter
from app.tasks.confirm import confirm_booking


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(session_factory):
    async def _override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def disable_rate_limit():
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def enqueue_mock(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(confirm_booking, "kiq", mock)
    return mock


@pytest.fixture
def booking_payload():
    plus_day_date = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    return {"name": "Ann Smith", "datetime": plus_day_date, "service_type": "haircut"}
