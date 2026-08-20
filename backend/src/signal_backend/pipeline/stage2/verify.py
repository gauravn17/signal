"""
Stage 2: deep verification, run only against the Stage 1 shortlist.

Agentic — the model decides what to investigate next per candidate based on
what it has already found (e.g. no GitHub -> check personal site; sparse
GitHub -> look at commit history; a specific claim -> attempt to verify it).
Produces cross-referenced findings, flagged disagreements between sources,
and an evidence-confidence rating. Bottlenecked by GitHub API rate limits,
so this only runs at funneled scale (~50-150 candidates), not full volume.
"""

from signal_backend.models import Candidate, JobDescription, MatchResult


def run_stage2(candidate: Candidate, job_description: JobDescription, stage1_result: MatchResult) -> MatchResult:
    raise NotImplementedError
