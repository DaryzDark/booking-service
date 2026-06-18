from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.bookings import router as bookings_router
from app.database import engine
from app.logging import configure_logging, get_logger
from app.rate_limit import limiter
from app.tasks.broker import broker

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    if not broker.is_worker_process:
        await broker.startup()
    logger.info("api_startup")
    yield
    if not broker.is_worker_process:
        await broker.shutdown()
    await engine.dispose()
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="Booking Service", version="0.1.0", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(bookings_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
