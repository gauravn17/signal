# AI Recruiting Fit Tool

## Purpose
A solo side project to learn distributed systems, agentic AI, and full-stack
engineering by building a tool for a problem I've personally lived: my team
had 1100 applicants for one role, and the hiring manager only interviewed the
5 candidates with referrals because reviewing 1100 resumes manually was
intractable. This tool helps traditional, resume-first hiring teams (not
just fast-moving AI-native startups) thoroughly review a large applicant
pool, so referrals aren't the only realistic path to an interview.

Not trying to replace referrals or convince teams to change their hiring
process (contrast with work-trial-first platforms like Rounds.so, which only
suit teams willing to adopt a new evaluation format). This tool front-loads
*before* the interview decision — going from "1100 unscreenable applicants"
to "a shortlist a hiring manager can actually read and trust."

Target user: traditional/enterprise tech hiring teams (e.g. a cloud security
team at a large company), not early-stage/AI-native startups.

## Core Design Principles
- **No black-box fit score.** Surface evidence + reasoning instead of a
  single number. A hiring manager should be able to see *why* the tool
  thinks something, not just trust a percentage.
- **Evidence confidence is a separate dimension from fit.** A candidate can
  be "strong fit, thin evidence" (great resume, no public work) or "moderate
  fit, strong evidence" (verified GitHub activity that's merely decent).
  Conflating these into one ranking defeats the transparency goal.
- **Thin evidence is not penalized** — candidates with little/no GitHub or
  personal site presence fall back to resume-stated experience, labeled
  clearly as lower-confidence rather than scored down.
- **Cross-referencing over isolated parsing.** The interesting signal is
  where sources agree or disagree (resume vs. GitHub vs. personal site
  timelines/claims), not just what each source says in isolation.
- **JDs get structured too.** Parse job descriptions into structured
  requirements (must-haves vs. nice-to-haves), including hiring-team-specific
  free-text criteria that a generic keyword filter would miss. This is what
  the candidate signal gets matched against.

## Data Sources
- Resume (self-reported baseline)
- GitHub (verify technical claims — real repos, commit authorship, activity
  timeline vs. claimed employment dates)
- Personal website, if present (verify framing/depth, check it's live)
- **Explicitly NOT LinkedIn** — no reliable free scraping option, and
  scraping violates LinkedIn's ToS with real legal/enforcement risk (see
  hiQ v. LinkedIn). Not worth building a product on that foundation.

## Architecture: Two-Stage Pipeline
**Stage 1 — cheap bulk pass (all candidates):**
Single structured-output LLM call per resume: extract fields, do basic
JD-requirement matching. Not agentic — fixed, cheap, fast. Funnels ~1000s of
candidates down to a shortlist (e.g. 50–150).

**Stage 2 — deep verification (funneled shortlist only):**
This is the actually agentic part. The model decides what to investigate
next per candidate based on what it's already found — e.g. no GitHub found →
check personal site instead; GitHub exists but sparse → look at commit
history; resume claims a specific award → attempt to verify it. Multi-step,
branching investigation, not a fixed sequence of calls. Output: a structured
profile with cross-referenced findings, flagged disagreements between
sources, and an evidence-confidence rating.

**Why two stages:** compute cost and GitHub API rate limits make deep
verification impractical at full volume (1000s of candidates), but cheap at
funneled scale (100s). Mirrors how a human recruiter would triage anyway.

## Distributed Systems Scope (honest framing)
At solo-project scale (hundreds–low thousands of resumes), true multi-node
infrastructure isn't required. What *is* in scope and worth building for
the learning goal:
- A job queue for the pipeline (single-machine is fine — Redis+RQ or Celery)
- Parallel/async processing of independent candidates in Stage 1
- Rate-limiting/backoff against external APIs (GitHub's ~5000/hr authenticated
  limit is the binding constraint, not compute)
- Clear separation between the cheap fan-out stage and the heavier,
  bottlenecked verification stage

## Tech Stack (tentative, not finalized)
- Web app (not native/mobile — recruiting review is a desk workflow)
- Python backend (FastAPI likely, given AI/extraction work is Python-native)
- Job queue for background pipeline processing
- DB for candidate profiles, JD requirements, and match results
- Simple frontend: JD + resume upload, dashboard to review structured
  candidate profiles (not a ranked score list)
- LLM: start with a free/open model via a free-tier host (e.g. Groq) for
  MVP iteration; swap to a stronger paid model later if reasoning quality
  in Stage 2 needs it. Stage 1 (structured extraction) should work fine on
  cheap/open models; Stage 2 (nuanced cross-referencing reasoning) is more
  likely to need a stronger model.
- Local-first development (local Postgres/SQLite, local Redis). Cloud
  deployment is a later step, not a prerequisite to prove out the concept.

## Explicitly Out of Scope (for now)
- ATS integration (v1 works from uploaded resumes/LinkedIn exports directly)
- LinkedIn scraping/data
- Multi-node distributed infrastructure
- Replacing or de-prioritizing referrals in the hiring process

## Competitive Landscape (for context, not action items)
- Most existing "AI resume screening" tools (commercial and open-source) do
  resume-vs-JD similarity/keyword matching, often via TF-IDF or a single
  LLM call. That's commoditized and is *not* what this project's
  differentiator is.
- Rounds.so takes the opposite approach: skip resume evaluation, test
  candidates directly with AI-driven work trials. Good fit for fast-moving,
  process-flexible teams; not a fit for traditional resume-first orgs, which
  is this project's target user.
- Sixtyfour AI (people-intelligence API) was considered as a possible
  verification/cross-referencing layer, but it leans into
  investigation/background-check framing — worth keeping in mind if
  compliance (e.g. FCRA-adjacent concerns) becomes relevant later.
- No product found (as of this writing) doing the specific combination this
  project targets: agentic, per-candidate cross-referencing of resume claims
  against live GitHub/site evidence with disagreement-flagging and
  confidence levels, instead of a similarity score.
