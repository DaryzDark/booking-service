# TaskIQ broker
from taskiq import TaskiqEvents, TaskiqState
from taskiq.middlewares import SmartRetryMiddleware
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from app.config import settings
from app.database import engine
from app.logging import configure_logging

broker = (
    RedisStreamBroker(url=settings.redis_url)
    .with_result_backend(RedisAsyncResultBackend(settings.redis_url))
    .with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=settings.max_retries,
            default_delay=settings.retry_base_delay,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=settings.retry_max_delay,
        )
    )
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _on_startup(_state: TaskiqState) -> None:
    configure_logging()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _on_shutdown(_state: TaskiqState) -> None:
    await engine.dispose()
