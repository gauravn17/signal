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
uv run rq worker stage2 --url redis://localhost:6379/0
```

## Tests

```
uv run pytest
```
