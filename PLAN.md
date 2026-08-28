# Signal — Stage 2 Implementation Plan

Working plan for the agentic deep-verification stage, broken into small steps
so each one can be picked up, implemented, tested, and committed independently
(e.g. by a `/loop` run: "implement the next unchecked item below, write tests
using fakes/mocks (no real network calls), run `uv run pytest`, commit, check
the box").

Context already in place: Stage 1 (`pipeline/stage1/`), the Groq-backed
`LLMClient` protocol in `services/llm.py`, SQLModel models in `models/`, and
API routers in `api/`. Follow the same conventions (Protocol + fake client for
tests, SQLModel for persistence, `uv run pytest` must pass before a step is
considered done).

## Steps

- [x] **1. GitHub service (`services/github.py`)**
  Wrapper around the GitHub REST API (via `httpx` or `requests`, using
  `settings.github_token`) exposing functions to fetch a user's public repos,
  a repo's commit history/authorship, and basic profile info. Handle rate
  limiting: read `X-RateLimit-Remaining`/`X-RateLimit-Reset` headers, raise a
  typed `GitHubRateLimitError` when exhausted rather than retrying forever.
  Test with a mocked HTTP client (`respx` or `unittest.mock`) — no real
  network calls, no real token needed.

- [x] **2. Website service (`services/website.py`)**
  Given a URL, check it's live (HTTP GET, follow redirects, timeout) and
  return status + raw text/HTML content (or `None` if unreachable). Test with
  mocked HTTP responses covering: live site, 404, timeout/connection error.

- [x] **3. Extend `LLMClient` for tool-calling**
  Add a method to the `LLMClient` protocol (e.g. `agentic_run(system, tools,
  tool_executor, response_model, max_steps)`) that runs a tool-calling loop:
  model picks a tool call or produces final structured output; loop executes
  the tool via `tool_executor` and feeds the result back; stops at
  `max_steps` or when the model returns a final answer. Implement on
  `GroqLLMClient` using Groq's OpenAI-compatible function-calling API. Write
  a `FakeLLMClient` variant in `tests/conftest.py` that scripts a fixed
  sequence of tool calls, so Stage 2 logic is testable without a real model.
  Flag if Groq's currently available models don't support reliable tool
  calling — fall back to a simpler fixed-sequence-with-early-exit design if so.

- [x] **4. Stage 2 orchestrator (`pipeline/stage2/verify.py`)**
  Replace the `NotImplementedError` stub. Given a `Candidate` + its Stage 1
  `MatchResult`, run the agentic loop with tools `check_github` and
  `check_website` (from steps 1–2). Branch per `CLAUDE.md`: no GitHub URL ->
  try the website; GitHub exists but sparse -> pull commit history; a
  specific resume claim (award, employer, dates) -> attempt to verify it
  against whatever evidence was gathered. Cap tool calls per candidate (e.g.
  max 5) to bound GitHub API usage.

- [x] **5. Disagreement-flagging + evidence-confidence output** (implemented as part of step 4 — same function in practice; tests cover thin/moderate/strong mapping)
  Final step of the Stage 2 loop: one structured-output call that takes all
  gathered tool results + the resume/Stage 1 claims and produces
  `findings` (cross-referenced, source-attributed), `disagreements` (explicit
  resume-vs-GitHub-vs-site conflicts), an `EvidenceConfidence` rating
  (thin/moderate/strong — thin means resume-only, not "low fit"), and a
  `fit_summary`. Persist as a `MatchResult(stage=PipelineStage.stage2_verification, ...)`.
  Unit test with the fake tool-calling client from step 3 asserting the
  mapping from gathered evidence to confidence level.

- [x] **6. API: trigger + retrieve Stage 2 verification**
  `POST /candidates/{id}/verify` — runs `run_stage2` synchronously for one
  candidate, stores and returns the resulting `MatchResult`. `GET
  /candidates/{id}` — returns the candidate plus both Stage 1 and Stage 2
  `MatchResult`s if present. Test via `TestClient` with the fake LLM/tool
  client, same pattern as `tests/test_api.py`.

- [x] **7. Shortlist selection endpoint**
  `POST /job-descriptions/{id}/shortlist` — accepts a list of candidate IDs
  (the hiring manager's manual picks from the Stage 1 dashboard, per
  `CLAUDE.md`'s "funnels 1000s down to 50-150" framing) and enqueues Stage 2
  for each. For now this can call `run_stage2` in a loop synchronously;
  background execution is step 8.

- [x] **8. Move Stage 2 to the Redis/RQ job queue**
  Wire up `rq` (already a dependency) with a worker process. Stage 2 calls
  from step 7 enqueue jobs instead of running inline; add a `GET
  /candidates/{id}/verify-status` (or similar) to poll job state. This is the
  "heavier, bottlenecked" stage from `CLAUDE.md`'s distributed-systems scope
  — Stage 1 stays synchronous/inline, only Stage 2 goes through the queue.
  Test with `rq`'s `SimpleWorker` run inline in-process (no real Redis
  network round-trip needed for the test, though local Redis via
  `docker-compose` is already available for manual testing).

- [x] **9. Manual end-to-end smoke test** — done via curl against real Groq +
  GitHub APIs (JD parse -> Stage 1 extract/match -> Stage 2 verify). Found
  and fixed three real bugs in the process: a decommissioned Groq model name,
  a macOS fork-safety crash in the RQ worker, and Stage 2's tool executor
  blowing through token-per-minute limits by dumping raw GitHub API payloads
  instead of trimmed fields. Deliberately tested with a mismatched real
  GitHub profile and confirmed Stage 2 correctly flagged the resulting
  disagreement rather than silently ignoring it.

## Explicitly deferred (not in this plan)

- Frontend/dashboard — comes after Stage 2 logic is proven via the API.
- `verify_claim`-style free-text claim verification via web search — no
  search tool wired up yet; out of scope until a source for that exists.
- Multi-node/distributed worker scaling — single local RQ worker is enough
  per `CLAUDE.md`'s honest-framing section.
