# Signal — Product Context & Current Thesis

## Product
Signal is an evidence-based candidate intelligence platform for traditional/enterprise hiring teams.

Core problem:
Hiring teams can receive hundreds or thousands of applications but cannot deeply review all of them. Existing ATS products primarily manage workflow and increasingly offer AI matching, but Signal's goal is to provide deeper, role-specific, comparative evaluation of the applicant pool.

Core promise:
> Given a job description and a large applicant pool, identify the candidates whose demonstrated qualifications most strongly match the actual requirements of the role, while showing the hiring manager the evidence and reasoning behind the assessment.

Signal should NOT be positioned as:
- "AI resume screening"
- a generic ATS replacement
- an opaque candidate scoring system
- an internet people-search/deep-research product
- simply a GitHub/resume verification tool

Potential positioning:
> "ATSs organize applicants. Signal helps you actually find the strongest candidates."
or
> "Signal is the evaluation intelligence layer for hiring."

## Important product philosophy

1. No black-box fit score as the primary output.
   - Surface evidence, reasoning, strengths, gaps, and uncertainty.
   - A hiring manager should understand why a candidate was surfaced.

2. Evidence confidence is separate from candidate fit.
   - Strong fit + thin evidence is possible.
   - Moderate fit + strong evidence is possible.
   - Lack of GitHub/website should NOT penalize a candidate.

3. Holistic evaluation.
   Evaluate the whole candidate against the specific role:
   - professional experience
   - responsibilities and ownership
   - technical skills
   - projects
   - accomplishments/impact
   - education
   - certifications
   - domain experience
   - seniority
   - recency
   - duration/depth
   - professional vs academic vs personal experience
   - scale/context where stated
   - any other information provided in the application

4. Do not treat keywords as qualifications.
   Example: 1,000 applicants may mention Kafka, but Signal should distinguish:
   - "used Kafka in a class project"
   - "built a Kafka personal project"
   - "used Kafka during an internship"
   - "used Kafka professionally for 2 years"
   - "designed/owned production Kafka infrastructure at large scale"

5. Relevance is contextual.
   The same experience can have different value for a junior vs senior role or for different job descriptions.

6. Education/certifications/etc. should only matter when relevant to the job.
   Avoid arbitrary prestige or credential scoring.

7. Human remains final decision maker.
   Signal should provide decision support, not make autonomous employment decisions.

## Candidate evaluation model

Think of evaluation as:

Candidate qualifications × role requirements × context × evidence

For each requirement, Signal should reason about:
- whether the candidate demonstrates it
- depth
- duration
- recency
- context
- scale
- responsibility/ownership
- impact
- seniority
- source/evidence quality

The UI should expose conclusions and supporting evidence rather than pretending these dimensions are objective numerical truths.

## Job description parsing

A JD should be structured into:
- must-have requirements
- preferred/nice-to-have requirements
- skills
- experience requirements
- responsibilities
- education requirements
- certifications
- domain/context
- seniority/level
- hiring-team-specific criteria/free text

The system should evaluate candidates against this structured representation rather than raw JD keyword overlap.

## Candidate profile

Resume/application information should be transformed into a structured candidate representation containing:
- employment history
- roles/titles
- durations
- responsibilities
- technologies
- projects
- achievements/metrics
- education
- certifications
- skills
- domain experience
- other relevant application information

## External evidence

External sources are OPTIONAL corroborating evidence, not the core product:
- GitHub
- personal website
- portfolio
- potentially other legally/ethically appropriate sources

No LinkedIn scraping dependency.

Important realization:
Exa and Sixtyfour already provide strong general-purpose people/web investigation capabilities. Therefore "agent deeply researches a candidate on the internet" is NOT Signal's moat.

Signal should potentially use Exa/Sixtyfour or similar tools as underlying external-evidence providers rather than compete with their generic research capability.

## Deep evaluation vs deep research

Deep research:
> "Find everything you can about this candidate."

Deep evaluation:
> "Given 1,137 applicants for THIS role, which candidates demonstrate the strongest evidence of meeting THIS hiring team's requirements, and why?"

Signal should focus on the second problem.

## Potential architecture

Stage 1 — broad/cheap evaluation:
1. Parse JD once into structured requirements.
2. Parse every resume/application into structured candidate profiles.
3. Holistically evaluate every candidate against the role.
4. Produce explainable preliminary assessments.
5. Funnel a large pool into a manageable candidate set.

Stage 2 — selective deep investigation:
1. Run only for shortlisted/high-value/uncertain candidates.
2. Agent decides what additional evidence is worth gathering.
3. Can inspect GitHub, websites, etc. when available.
4. Resolve specific claims/uncertainties rather than blindly researching everyone.
5. Produce source-attributed findings and explicit conflicts/unknowns.

Important: Stage 2 should be a bottlenecked background job, not a blocking API request.

## Agent behavior

The agent should investigate specific uncertainties.

Example:
Resume:
> "Designed a distributed Kafka system processing 50M events/day."

Agent can:
1. identify the claim
2. assess what evidence is already present
3. decide whether external verification is valuable
4. inspect relevant public repositories/site if available
5. check authorship/timeline/project details
6. compare evidence
7. stop once sufficient evidence exists
8. report what is supported, unsupported, contradictory, or unknown

Never turn "no external evidence found" into "candidate is suspicious."

## Example output

Candidate A — Strong Match

Required:
- Distributed systems — Strong
  4 years professional backend/distributed systems experience; resume describes ownership of production event-processing infrastructure.
- Kafka — Strong
  2.5 years professional use.
- Python — Strong
  Primary language in current/previous roles.
- AWS — Strong/Moderate depending on evidence.
- IAM/security — Strong if demonstrated through actual work.

Preferred:
- Kubernetes — Moderate/Strong
- CS degree — Yes
- AWS certification — Yes

Additional strengths:
- production ownership
- relevant scale
- increasing responsibility

Evidence confidence:
Strong

Potential gaps:
- no direct evidence for X
- scope of Y unclear

Do not output simply:
> Fit score: 92.7%

## Core startup thesis

The startup opportunity is NOT "AI recruiting" broadly. Recruiting AI is crowded.

Existing/adjacent competitors include:
- ATS platforms such as Greenhouse and Ashby, which increasingly have AI candidate matching/review
- Eightfold and other talent intelligence platforms
- Exa for web/candidate research
- Sixtyfour for people/entity intelligence and web investigation
- newer AI recruiting startups such as Olive

Therefore Signal needs differentiation.

Current differentiated thesis:
> Signal is the role-specific evaluation intelligence layer that learns/represents the hiring team's actual requirements and performs transparent, comparative, evidence-backed evaluation across the entire applicant pool.

Potential wedge:
> Do not replace the ATS initially. Integrate with existing ATSs and accept the applicant pool, then produce an evidence-backed shortlist.

Potential value proposition:
> "Your ATS is the database. Signal is the intelligence layer that helps you find the needle."

## Critical validation experiment

Do not validate with generic recruiter enthusiasm.

Best test:
- Obtain 500–1,000 anonymized historical applications for a role that was already filled.
- Obtain the actual human shortlist/interview/hire outcomes if possible.
- Run Signal on the historical applicant pool.
- Compare:
  1. ATS ranking
  2. Signal evaluation
  3. experienced human-selected candidates

Key question:
> Can Signal consistently surface the candidates humans ultimately considered strong, while reducing human review effort and providing understandable evidence for why?

Potential metrics:
- recall of human shortlist
- precision of surfaced candidates
- reduction in review time
- recruiter/hiring-manager agreement
- evidence usefulness
- false-positive/false-negative patterns
- consistency across different JDs
- fairness/bias evaluation

## Regulatory/product caution

Employment screening is high-risk. Signal should avoid presenting itself as an autonomous hiring decision maker.

Design for:
- human oversight
- transparency
- explainability
- auditability
- evidence traceability
- configurable criteria
- bias/fairness testing
- appropriate legal review before production use

## Current MVP concept

Frontend:
- job creation
- JD input
- applicant/resume upload
- applicant pool dashboard
- candidate comparison
- candidate detail/evidence view
- shortlist/review workflow
- Stage 2 verification status

Backend:
- Python/FastAPI
- Postgres / SQLModel
- Redis + RQ background jobs
- LLM via OpenAI-compatible client (currently Groq for MVP experimentation)
- resume parser
- GitHub client
- website checker
- agentic Stage 2 service

Local:
- Docker Compose for Postgres + Redis

Current repository concept:
signal/
├── CLAUDE.md
├── PLAN.md
├── docker-compose.yml
└── backend/
    └── src/signal_backend/
        ├── main.py
        ├── config.py
        ├── jobs.py
        ├── models/
        ├── api/
        ├── pipeline/
        │   ├── stage1/
        │   └── stage2/
        ├── services/
        │   ├── llm.py
        │   ├── github.py
        │   ├── website.py
        │   ├── resume_parser.py
        │   ├── queue.py
        │   └── stage2_service.py
        └── tests/

## Deployment direction

MVP can be deployed without complex infrastructure:
- Frontend: Vercel
- FastAPI: Render/Railway/Fly.io or AWS
- Postgres: managed Postgres (Neon/Supabase/Railway/etc.)
- Redis: managed Redis/Upstash
- RQ worker: separate worker process
- LLM: Groq initially
- GitHub API for optional evidence

Later, move to AWS/ECS/RDS/ElastiCache if scale/learning goals justify it.

Do NOT overengineer distributed infrastructure for hundreds/low-thousands of resumes.

## Current product positioning to test

Primary:
> Evidence-based candidate intelligence for high-volume hiring.

Alternative:
> Find the strongest candidates in your applicant pool — with evidence, not black-box scores.

Potential tagline:
> "Turn an unsearchable applicant pool into an evidence-backed shortlist."

## Open questions that still need validation

1. Can Signal materially outperform modern ATS AI matching?
2. Does holistic comparative evaluation provide enough incremental value to justify a separate product?
3. Which hiring teams feel the pain most strongly?
4. What specific information do hiring managers wish they could evaluate but currently cannot?
5. Would teams pay for a layer on top of their ATS?
6. Is the best wedge SWE/technical hiring, where skills/projects/experience are more structured?
7. How should Signal handle fairness and employment-law requirements?
8. What is the best evaluation benchmark for "good candidate selection"?
9. How much external investigation is actually useful after holistic resume evaluation?
10. Can the system learn an organization's hiring bar without becoming an opaque model?

## Important instruction for future implementation

Do not blindly implement the original "resume → GitHub deep research → shortlist" concept.

The current thesis has evolved:
1. Holistic candidate evaluation is the core.
2. Comparative evaluation across the applicant pool is the core value.
3. External deep investigation is optional evidence enrichment.
4. Exa/Sixtyfour can potentially be tools/providers, not the product's moat.
5. Explainability/evidence is essential.
6. Human decision-making remains central.
7. Validate against historical real-world hiring outcomes before assuming the ranking/evaluation is useful.

When making architecture decisions, prioritize a credible MVP and measurable validation over adding flashy agentic features.
