"""
Behavioral/semantic tests against the REAL Groq model — these test whether
the model's judgment actually reflects the invariants Stage 1 depends on
(depth vs. keyword, context, seniority-from-evidence, etc.), which a canned
FakeLLMClient can't verify. Skipped automatically without a configured
LLM_API_KEY. Focused on behavioral invariants, not exact labels, since live
model output is inherently variable in wording.
"""

from uuid import uuid4

import pytest

from signal_backend.config import settings
from signal_backend.models import Candidate, JobDescription
from signal_backend.pipeline.stage1.extract import run_stage1
from signal_backend.pipeline.stage1.parse_jd import parse_job_description

pytestmark = pytest.mark.skipif(
    not settings.llm_api_key, reason="requires a real LLM_API_KEY to test semantic behavior against the live model"
)

JD_TEXT = """
We are hiring a Senior Backend Engineer.

Requirements:
- Production experience with Apache Kafka.
- Experience with Kubernetes.
- Strong system design and architecture experience, with ownership of technical decisions.
- Proficient in React (frontend).
- Bachelor's degree in Computer Science or related field.
"""

# Deliberately: Kafka via a class project only (shallow/academic), no
# Kubernetes mention at all, a "Senior" title paired with explicitly junior
# duties, and React used as an old hobby project — probes keyword-vs-depth,
# academic-vs-professional, unsupported-claim handling, seniority-from-title,
# and recency all in one resume.
SHALLOW_RESUME = """
Alex Chen
alex.chen@example.com

Education:
B.S. Computer Science, State University, 2020.

Experience:
Senior Software Engineer, SmallCo (2020-2023)
- Fixed minor bugs in the codebase under close supervision from senior teammates.
- Followed existing design patterns; did not make architectural or design decisions.
- Used React for a few small UI tweaks as a hobby side project in 2015-2016, before joining SmallCo.

Projects:
- Built a Kafka-based message queue for a university class project (Distributed Systems course, 2019).
"""

# Deliberately: Kafka + Kubernetes in production with real scale/ownership,
# explicit architectural ownership (earning seniority through substance, not
# title), and React described as current/ongoing — the comparison partner
# for every invariant above.
DEEP_RESUME = """
Jordan Smith
jordan.smith@example.com

Education:
B.S. Computer Science, Tech University, 2018.

Experience:
Senior Backend Engineer, BigTech Inc (2020-Present)
- Designed and led the architecture for a company-wide Kafka-based event streaming
  platform processing 50 million events per day in production, making all major
  technical decisions independently.
- Deployed and operated production Kubernetes clusters serving the platform's
  microservices.
- Currently building and maintaining React-based internal dashboards used daily
  by the engineering team.
"""

ASSESSMENT_ORDER = {"not_demonstrated": 0, "weak": 1, "moderate": 2, "strong": 3}


@pytest.fixture(scope="module")
def jd():
    org_id = uuid4()
    requirements = parse_job_description(JD_TEXT)
    return JobDescription(
        organization_id=org_id, title="Senior Backend Engineer", raw_text=JD_TEXT, requirements=requirements
    )


def _evaluate(jd, resume_text):
    candidate = Candidate(organization_id=jd.organization_id, job_description_id=jd.id, resume_raw_text=resume_text)
    match_result = run_stage1(candidate, jd)
    return candidate, match_result


def _finding_for(match_result, keyword):
    matches = [f for f in match_result.findings if keyword.lower() in f["requirement_text"].lower()]
    assert matches, f"No requirement matching {keyword!r} found in {[f['requirement_text'] for f in match_result.findings]}"
    return matches[0]


@pytest.fixture(scope="module")
def shallow_result(jd):
    return _evaluate(jd, SHALLOW_RESUME)


@pytest.fixture(scope="module")
def deep_result(jd):
    return _evaluate(jd, DEEP_RESUME)


def test_keyword_mention_scores_lower_than_meaningful_experience(shallow_result, deep_result):
    _, shallow = shallow_result
    _, deep = deep_result
    shallow_kafka = _finding_for(shallow, "Kafka")["assessment"]
    deep_kafka = _finding_for(deep, "Kafka")["assessment"]
    assert ASSESSMENT_ORDER[shallow_kafka["assessment"]] < ASSESSMENT_ORDER[deep_kafka["assessment"]]
    assert shallow_kafka["assessment"] != "strong"
    assert deep_kafka["assessment"] == "strong"


def test_academic_vs_professional_context_is_distinguished(shallow_result, deep_result):
    _, shallow = shallow_result
    _, deep = deep_result
    shallow_kafka = _finding_for(shallow, "Kafka")["assessment"]
    deep_kafka = _finding_for(deep, "Kafka")["assessment"]
    assert shallow_kafka["context"] in ("academic", "personal")
    assert deep_kafka["context"] == "professional"


def test_unsupported_requirement_is_not_demonstrated_without_fabrication(shallow_result):
    _, shallow = shallow_result
    kubernetes = _finding_for(shallow, "Kubernetes")["assessment"]
    assert kubernetes["assessment"] == "not_demonstrated"
    assert kubernetes["evidence"] == []
    assert kubernetes["gaps"]


def test_recency_reflects_stated_dates(shallow_result, deep_result):
    _, shallow = shallow_result
    _, deep = deep_result
    shallow_react = _finding_for(shallow, "React")["assessment"]
    deep_react = _finding_for(deep, "React")["assessment"]
    # The shallow resume explicitly states 2015-2016; the model shouldn't
    # describe decade-old hobby use as current.
    shallow_recency = (shallow_react["recency"] or "").lower()
    assert "current" not in shallow_recency and "present" not in shallow_recency
    # The deep resume explicitly says "Currently" / "Present" — that should
    # be reflected, not treated as unknown.
    assert deep_react["recency"] is not None


def test_seniority_reflects_described_work_not_job_title(shallow_result, deep_result):
    _, shallow = shallow_result
    _, deep = deep_result
    shallow_design = _finding_for(shallow, "system design")["assessment"]
    deep_design = _finding_for(deep, "system design")["assessment"]
    # Candidate A has a "Senior" title but explicitly junior-described duties
    # (no architectural ownership) — must not score strong on title alone.
    assert shallow_design["assessment"] != "strong"
    # Candidate B earns strong ownership through described substance.
    assert deep_design["assessment"] == "strong"


def test_no_github_or_website_does_not_lower_evidence_confidence(shallow_result, deep_result):
    shallow_candidate, shallow = shallow_result
    deep_candidate, _ = deep_result
    assert shallow_candidate.github_url is None
    assert deep_candidate.github_url is None
    # The deep resume is detailed/specific despite having no external links
    # at all — evidence_confidence must reflect resume detail, not penalize
    # for missing GitHub/website.
    assert deep_result[1].evidence_confidence.value in ("moderate", "strong")
