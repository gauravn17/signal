# signal-backend

## Dev setup

```
docker compose up -d          # from ~/signal — Postgres + Redis
cp .env.example .env          # then fill in LLM_API_KEY / GITHUB_TOKEN
uv run uvicorn signal_backend.main:app --reload
```

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
