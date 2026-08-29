# signal-backend

## Dev setup

```
docker compose up -d          # from ~/signal — Postgres + Redis
cp .env.example .env          # then fill in LLM_API_KEY / GITHUB_TOKEN
uv run alembic upgrade head   # apply migrations — the app no longer creates tables on boot
uv run uvicorn signal_backend.main:app --reload
```

Schema changes go through Alembic now (`uv run alembic revision --autogenerate -m "..."` then
review the generated migration before committing it — autogenerate misses some changes, e.g.
column renames look like a drop+add). Tests apply migrations automatically once per session.

Stage 2 verification runs on a background job queue (RQ). Start a worker
alongside the API to process it:

```
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run rq worker stage2 --url redis://localhost:6379/0
```

The `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` env var works around a macOS-only
crash (`+[NSMutableString initialize] may have been in progress in another
thread when fork() was called`) — RQ's default worker forks a subprocess per
job, and `truststore` (an `openai` client dependency that bridges to macOS's
Objective-C Security framework for TLS) isn't fork-safe. Not needed on Linux.

## Tests

```
uv run pytest
```
