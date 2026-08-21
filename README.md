# Signal

Signal is a tool that helps traditional, resume-first hiring teams actually
review a large applicant pool — instead of only interviewing the handful of
candidates who got a referral.

## The problem

A team I worked with posted one role and got **1,100 applicants**. The
hiring manager ended up interviewing exactly **5 people — all of whom had a
referral** — because manually reading 1,100 resumes was never going to
happen. Everyone else, no matter how qualified, never got a real look.

That's the failure mode Signal targets: not "hiring managers are lazy," but
"1,100 resumes is an intractable amount of reading for a human." Signal
doesn't try to replace referrals or convince teams to change how they
interview. It front-loads the work *before* the interview decision — turning
"1,100 unscreenable applicants" into a shortlist a hiring manager can
actually read and trust.

This is also a solo learning project — a way to get hands-on with agentic
AI, a real backend, and a (small-scale, honestly-scoped) distributed
pipeline, by building something for a problem I've personally lived.

## Who it's for

Traditional/enterprise hiring teams (think: a software team at a large
company), not early-stage, AI-native startups already comfortable with
unconventional hiring processes. If your team would consider a platform like
[Rounds.so](https://rounds.so) — which skips resume review entirely and
evaluates candidates via work trials — Signal probably isn't for you. Signal
is for teams that still read resumes, but currently can't read *enough* of
them.

## Design principles

These shape almost every architectural decision below, so it's worth
stating them up front:

- **No black-box fit score.** Signal surfaces evidence and reasoning, not a
  single number. A hiring manager should be able to see *why* the tool
  thinks something, not just trust a percentage.
- **Evidence confidence is separate from fit.** A candidate can be "strong
  fit, thin evidence" (great resume, no public work to check it against) or
  "moderate fit, strong evidence" (verified GitHub activity that's merely
  decent). Collapsing those into one ranking would defeat the point.
- **Thin evidence is not penalized.** A candidate with no GitHub or personal
  site isn't scored down — they fall back to resume-stated experience,
  clearly labeled as lower-confidence rather than worse.
- **Cross-referencing over isolated parsing.** The interesting signal is
  *where sources agree or disagree* — resume vs. GitHub vs. personal site —
  not what any single source says on its own.
- **Job descriptions get structured too.** JDs are parsed into
  must-have/nice-to-have requirements, including hiring-team-specific free
  text a generic keyword filter would miss. Candidate signal gets matched
  against this structure, not raw JD text.

## Data sources

| Source | What it's used for |
|---|---|
| Resume | Self-reported baseline — the starting claims to verify |
| GitHub | Verifying technical claims: real repos, commit authorship, activity timeline vs. claimed employment dates |
| Personal website (if any) | Checking it's live and whether its framing/depth matches the resume |
| ~~LinkedIn~~ | **Explicitly not used** — no reliable free/legal scraping option (see *hiQ v. LinkedIn*); not worth building on that foundation |

## Architecture: a two-stage pipeline

The core insight: verifying a candidate against live external evidence
(GitHub API calls, website checks, multi-step reasoning) is too slow and
too rate-limited to run on *every* applicant. But triaging resumes against a
JD is cheap. So the pipeline is split accordingly — mirroring how a human
recruiter would triage anyway.

```
                 ┌─────────────────────────────────────────────┐
                 │  Stage 1 — cheap bulk pass (every candidate) │
                 │                                               │
  Resume ───────▶│  One fixed LLM call: extract resume fields,  │
                 │  match against the JD's structured            │
                 │  requirements. Not agentic. Cheap. Fast.       │
                 └─────────────────────┬─────────────────────────┘
                                        │
                          funnels 1,000s of candidates
                          down to a shortlist (50-150)
                                        │
                                        ▼
                 ┌─────────────────────────────────────────────┐
                 │  Stage 2 — deep verification (shortlist only)│
                 │                                               │
                 │  Agentic: the model decides what to check     │
                 │  next based on what it's already found —      │
                 │  no GitHub? try the site. GitHub sparse?       │
                 │  pull commit history. Specific claim? try to   │
                 │  verify it. Runs as a background job.          │
                 └─────────────────────┬─────────────────────────┘
                                        │
                                        ▼
                 Structured profile: findings, flagged
                 disagreements between sources, and an
                 evidence-confidence rating (thin/moderate/strong)
```

**Why split it this way:** GitHub's API allows roughly 5,000 authenticated
requests/hour, and multi-step agentic reasoning has real compute cost.
Neither is viable at "every applicant" scale, but both are perfectly
affordable once you've already narrowed 1,000s of resumes down to a
hiring manager's shortlist. Stage 1 does that narrowing; Stage 2 does the
real investigative work.

### Stage 1 — cheap bulk pass

For every candidate: one structured-output LLM call
(`pipeline/stage1/extract.py`) that extracts resume fields (skills, years of
experience, employment history, education) and checks each one against the
JD's requirements, noting whether it's met, partially met, or not met — with
a cited excerpt as evidence, not a score. Job descriptions themselves are
parsed once, up front, into structured requirements
(`pipeline/stage1/parse_jd.py`) — must-have vs. nice-to-have, and flagging
hiring-team-specific free text a keyword filter would miss.

### Stage 2 — deep verification

For the hiring manager's shortlisted picks only: an *agentic* loop
(`pipeline/stage2/verify.py`) where the model has tools to check a
candidate's GitHub profile/repos, pull a specific repo's commit history, or
check whether their personal site is live — and decides which to use and in
what order, branching based on what it finds. It stops once it's gathered
enough to produce:

- **findings** — specific, source-attributed observations (resume, GitHub,
  or website), each marked as supporting, contradicting, or neutral
- **disagreements** — explicit conflicts between sources (e.g. resume says
  2019–2025 at a company, but GitHub commit history tells a different
  story)
- **evidence_confidence** — `thin` / `moderate` / `strong`, describing how
  much external corroboration was found — *not* a fit judgment. A
  no-GitHub, no-website candidate lands at `thin`, not "worse."
- **fit_summary** — a plain-language summary, never a number

Because this stage is the bottlenecked one (GitHub rate limits, multi-step
reasoning cost), it doesn't run inline in an API request — it's handed off
to a background job queue (see below) so the API stays responsive.

## What "distributed systems" means here (honestly)

This is a solo project at hundreds-to-low-thousands-of-resumes scale, not a
system that needs real multi-node infrastructure — and it doesn't pretend
otherwise. What *is* in scope, and actually implemented:

- **A background job queue** (Redis + [RQ](https://python-rq.org/)) so
  Stage 2 doesn't block API requests
- **Rate-limit-aware external API calls** — the GitHub client reads
  `X-RateLimit-Remaining`/`X-RateLimit-Reset` headers and raises a typed
  error rather than silently retrying into a wall
- **A clear boundary between the cheap fan-out stage and the heavier,
  bottlenecked verification stage** — enforced structurally, not just by
  convention (Stage 2 literally can't run until a Stage 1 result exists)

Explicitly *not* in scope: multi-node worker clusters, distributed
consensus, sharding — none of that is needed at this project's scale, and
pretending otherwise would just be resume-driven-development in the bad
sense.

## How a request actually flows

1. **Create a job description** — `POST /job-descriptions` with a title and
   raw text. The JD is parsed into structured requirements immediately and
   stored.
2. **Upload candidates** — `POST /candidates` (multipart form: JD id, name,
   optional email/GitHub/website URLs, and a resume file — PDF or plain
   text). Stage 1 runs synchronously in the same request: the resume is
   extracted and matched against the JD, and a Stage 1 `MatchResult` comes
   back immediately.
3. **Review the Stage 1 shortlist** — `GET /candidates?job_description_id=…`
   lists everyone with their Stage 1 result. This is where a hiring manager
   picks who's worth deeper investigation (the funnel from 1,000s down to
   50–150 from `CLAUDE.md`'s framing).
4. **Kick off Stage 2** — either `POST /candidates/{id}/verify` for one
   candidate, or `POST /job-descriptions/{id}/shortlist` with a list of
   candidate IDs to batch-enqueue several at once. Both *enqueue* a
   background job rather than blocking.
5. **Poll for results** — `GET /jobs/{job_id}` returns the job's status
   (`queued` / `started` / `finished` / `failed`) and, once finished, the
   resulting Stage 2 `MatchResult`.
6. **See everything together** — `GET /candidates/{id}` returns the
   candidate plus every `MatchResult` recorded for them, Stage 1 and Stage 2
   side by side.

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| Backend | Python, [FastAPI](https://fastapi.tiangolo.com/) | AI/extraction work is Python-native; FastAPI gives typed request/response models for free |
| Data layer | [SQLModel](https://sqlmodel.tiangolo.com/) over Postgres | Pydantic-native ORM — the same field validation doubles as the API schema |
| Job queue | Redis + [RQ](https://python-rq.org/) | Simple, single-machine-friendly queue; RQ specifically because it's low-ceremony compared to Celery for a solo project |
| LLM | [Groq](https://groq.com/), via an OpenAI-compatible client | Free-tier-friendly for MVP iteration; the client is written against the generic OpenAI tool-calling interface, so swapping providers later is a `base_url`/model change, not a rewrite |
| Package management | [uv](https://docs.astral.sh/uv/) | Fast, single tool for venv + deps + lockfile |
| Local dev | Docker Compose (Postgres + Redis) | Reproducible, no host-installed database required |

## Repository layout

```
signal/
├── CLAUDE.md                    # project brief / design doc
├── PLAN.md                      # step-by-step Stage 2 build plan
├── docker-compose.yml           # local Postgres + Redis
└── backend/
    └── src/signal_backend/
        ├── main.py               # FastAPI app, router wiring, table creation
        ├── config.py             # settings (DB/Redis URLs, API keys) via .env
        ├── jobs.py                # RQ job entry points (run in the worker process)
        ├── models/                # SQLModel tables: Candidate, JobDescription, MatchResult
        ├── api/                   # HTTP routes: job_descriptions, candidates, jobs
        ├── pipeline/
        │   ├── stage1/            # cheap bulk extraction + JD requirement parsing
        │   └── stage2/            # agentic deep verification
        ├── services/
        │   ├── llm.py             # Groq-backed LLM client (structured output + tool-calling loop)
        │   ├── github.py          # GitHub API client with rate-limit handling
        │   ├── website.py         # personal-site liveness/content check
        │   ├── resume_parser.py   # PDF/text resume extraction
        │   ├── queue.py           # Redis/RQ queue setup
        │   └── stage2_service.py  # shared Stage 2 trigger logic (used by both the API and the RQ job)
        └── tests/                 # pytest suite — all external calls mocked/faked, no real network needed
```

## Running it locally

```bash
cd signal
docker compose up -d                     # Postgres + Redis
cd backend
cp .env.example .env                     # then fill in LLM_API_KEY (Groq) and GITHUB_TOKEN
uv run uvicorn signal_backend.main:app --reload
```

Stage 2 needs a worker running alongside the API to actually process
verification jobs:

```bash
uv run rq worker stage2 --url redis://localhost:6379/0
```

Run the test suite (no real API keys required — the LLM and GitHub clients
are faked/mocked):

```bash
uv run pytest
```

## Status

Stages 1 and 2 of the pipeline are implemented end-to-end, backed by tests
that don't require real API keys or network access. See `PLAN.md` for the
step-by-step build log of Stage 2, and `CLAUDE.md` for the full original
project brief, including what's explicitly out of scope for now
(ATS integration, LinkedIn data, multi-node infrastructure, and a frontend —
the project currently exposes its functionality as an API rather than a UI).
