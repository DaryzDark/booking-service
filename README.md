# Booking Service

Асинхронный сервис записи на встречи. Клиент создаёт бронь через REST API, она
сохраняется со статусом `pending` и ставится в очередь; воркер асинхронно
подтверждает её (имитируя сбойный внешний сервис), логирует mock-уведомление, и
бронь переходит в `confirmed` или `failed`.

**Стек:** FastAPI · TaskIQ (Redis — брокер и result backend) · PostgreSQL
(SQLAlchemy 2.0 async + Alembic) · structlog · slowapi.

## Требования

| Инструмент | Версия | Зачем |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) | 24+ | запуск всего стека через `compose` |
| [Docker Compose](https://docs.docker.com/compose/) | v2+ (`compose` plugin) | оркестрация сервисов |
| [Python](https://www.python.org/downloads/) | 3.13+ | только для локального запуска тестов |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | 0.5+ | только для локального запуска тестов |

> Для запуска через `docker compose` Python и uv на хосте **не нужны** — всё собирается внутри контейнера.

## Запуск

Весь стек поднимается одной командой:

```bash
docker compose up --build # либо: make dev
```

Поднимаются Postgres, Redis, применяются миграции (одноразовый сервис `migrate`),
затем стартуют API и воркер. API доступен на <http://localhost:8000>.

Настройки можно переопределить через `.env`.

## Тесты

Тесты используют SQLite в памяти, брокер замокан — поднимать docker нет необходимости:

```bash
uv sync          # создать окружение  и поставить зависимости
uv run pytest    # либо: make test
```


## API

| Метод  | Путь              | Описание                                                        |
|--------|-------------------|-----------------------------------------------------------------|
| POST   | `/bookings`       | Создать бронь (`name`, `datetime`, `service_type`). Rate limit. |
| GET    | `/bookings/{id}`  | Статус брони (`pending` / `confirmed` / `failed` / `cancelled`).|
| GET    | `/bookings`       | Список: фильтр `?status=`, пагинация `?limit=&offset=`.         |
| DELETE | `/bookings/{id}`  | Отмена брони (только в статусе `pending`).                       |

Пример:

```bash
curl -X POST localhost:8000/bookings -H 'content-type: application/json' \
  -d '{"name":"Anna","datetime":"2030-01-01T10:00:00Z","service_type":"haircut"}'
```

## Технические решения

**Выбор инструментов.** FastAPI — асинхронный. Очередь — **TaskIQ**, 
выбран  как async-native и заточенный под FastAPI; Redis при этом
остаётся брокером и result backend (`taskiq-redis`).
БД — PostgreSQL через SQLAlchemy 2.0
(async ORM, без сырого SQL) с миграциями Alembic.

**Структура задачи.**

- **Постановка в очередь.** Эндпоинт сначала сохраняет бронь (`commit`) и только потом
  ставит задачу `confirm_booking.kiq(id)`. Порядок важен: поставь задачу до коммита — и
  воркер может взять её раньше, чем строка появится в БД, и не найти бронь.
- **Логика отдельно от обёртки.** Вся обработка — в обычной функции
  `confirm_booking_logic()`; тонкая обёртка `@broker.task` лишь достаёт номер попытки и
  вызывает её. Поэтому логику тестируем напрямую, без брокера и Redis.
- **Обработка в воркере.** Воркер вызывает «внешний сервис» (мок, падает ~15%). Успех →
  статус `confirmed` и лог mock-уведомления. Ошибка → задача бросает исключение, и
  `SmartRetryMiddleware` повторяет её с экспоненциальной задержкой; когда попытки
  исчерпаны — статус `failed`.

**Подход к идемпотентности.** Источник истины — статус брони в БД. Любой переход
делается одним условным `UPDATE ... WHERE id = :id AND status = 'pending'`. Если
обновилось 0 строк — бронь уже обработана, в терминальном статусе или отменена, и задача
становится no-op(переход из любого другого статуса обратно в `pending` невозможен). Поэтому повторный запуск с тем же `booking_id` не создаёт дубль
уведомления (оно отправляется только при реальном переходе) и не ломает статус;
отдельная таблица «обработанных задач» не нужна. 

**Прочее.** Отмена — soft delete (`pending → cancelled`, отмена не-`pending` брони → `409`);
логи — structlog в JSON; rate limiting — slowapi на `POST /bookings` (`10/minute`).

## Структура

```
app/
  main.py        # фабрика приложения + lifespan
  config.py      # настройки из env / .env
  database.py    # async engine + зависимость сессии (общая для API и воркера)
  models.py      # модель Booking + BookingStatus
  schemas.py     # Pydantic-схемы
  repository.py  # доступ к данным, включая идемпотентный transition_status()
  api/
    bookings.py  # FAST API endpoints
  tasks/
    broker.py    # брокер TaskIQ: Redis + SmartRetryMiddleware
    confirm.py   # задача confirm_booking + логика
alembic/         # миграции
tests/           # тесты API и логики воркера 
```
