import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCandidate, getJobStatus, verifyCandidate } from "../api/client";
import type { CandidateDetail, EvidenceConfidence, MatchResult } from "../api/types";
import { Badge, Button, Card, ErrorBanner, Spinner } from "../components/ui";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

const POLL_INTERVAL_MS = 2000;

const EVIDENCE_LABELS: Record<EvidenceConfidence, string> = {
  thin: "Evidence: thin",
  moderate: "Evidence: moderate",
  strong: "Evidence: strong",
};

const EVIDENCE_NOTES: Record<EvidenceConfidence, string> = {
  thin: "Thin means the assessment is based on the resume alone — it is not a quality judgment and not a worse candidate.",
  moderate: "Moderate means some outside evidence (e.g. GitHub, portfolio) was found alongside the resume.",
  strong: "Strong means multiple independent sources corroborated the resume's claims.",
};

const EVIDENCE_TONE: Record<EvidenceConfidence, "caution" | "info" | "positive"> = {
  thin: "caution",
  moderate: "info",
  strong: "positive",
};

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

// Four distinct states, not three — "no evidence either way" and "actively
// contradicted" must never collapse into one bucket. See CLAUDE.md: absence
// of proof is not proof of absence, and conflating the two misleads a
// hiring manager into treating a thin-evidence candidate as suspicious.
type FindingStatus = "supported" | "contradicted" | "no_evidence_found" | "not_investigated";

function findingStatus(value: unknown): FindingStatus {
  const s = asString(value)?.toLowerCase();
  if (s === "supported" || s === "contradicted" || s === "no_evidence_found" || s === "not_investigated") {
    return s;
  }
  return "not_investigated";
}

const STATUS_STYLES: Record<FindingStatus, string> = {
  supported: "border-emerald-200 bg-emerald-50 text-emerald-800",
  contradicted: "border-rose-200 bg-rose-50 text-rose-800",
  no_evidence_found: "border-slate-200 bg-slate-50 text-slate-700",
  not_investigated: "border-slate-100 bg-white text-slate-500",
};

const STATUS_LABELS: Record<FindingStatus, string> = {
  supported: "Supported",
  contradicted: "Contradicted — review",
  no_evidence_found: "No evidence found",
  not_investigated: "Not investigated",
};

function FindingsList({ findings }: { findings: Record<string, unknown>[] }) {
  if (findings.length === 0) {
    return <p className="text-sm italic text-slate-500">No findings recorded.</p>;
  }

  return (
    <ul className="space-y-2">
      {findings.map((finding, idx) => {
        const text = asString(finding.text) ?? asString(finding.finding) ?? JSON.stringify(finding);
        const source = asString(finding.source);
        const status = findingStatus(finding.status);

        return (
          <li key={idx} className={`rounded-lg border px-3.5 py-2.5 text-sm ${STATUS_STYLES[status]}`}>
            <div className="flex items-start justify-between gap-3">
              <p className="flex-1">{text}</p>
              <span className="shrink-0 rounded-full border border-current/30 bg-white/60 px-2 py-0.5 text-xs font-medium">
                {STATUS_LABELS[status]}
              </span>
            </div>
            {source && <p className="mt-1 text-xs opacity-75">Source: {source}</p>}
          </li>
        );
      })}
    </ul>
  );
}

function DisagreementsList({ disagreements }: { disagreements: Record<string, unknown>[] }) {
  if (disagreements.length === 0) {
    return null;
  }

  return (
    <div className="mt-5">
      <h4 className="text-sm font-semibold text-rose-800">Disagreements</h4>
      <p className="mb-2 text-xs text-slate-500">
        Places where outside evidence conflicts with what the resume claims.
      </p>
      <ul className="space-y-3">
        {disagreements.map((d, idx) => {
          const topic = asString(d.topic) ?? "Unspecified topic";
          const resumeClaim = asString(d.resume_claim) ?? "(not stated)";
          const evidenceFound = asString(d.evidence_found) ?? "(not stated)";

          return (
            <li key={idx} className="rounded-lg border border-rose-200 bg-rose-50 p-3.5">
              <p className="text-sm font-semibold text-rose-900">{topic}</p>
              <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-rose-200 bg-white p-2.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Resume claims</p>
                  <p className="mt-1 text-sm text-slate-800">{resumeClaim}</p>
                </div>
                <div className="rounded-md border border-rose-200 bg-white p-2.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Evidence found</p>
                  <p className="mt-1 text-sm text-slate-800">{evidenceFound}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MatchResultCard({ result }: { result: MatchResult }) {
  const stageLabel = result.stage === 1 ? "Stage 1 · Initial screen" : "Stage 2 · Verified";

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone={result.stage === 1 ? "neutral" : "primary"} className="px-3 py-1">
          {stageLabel}
        </Badge>
        {result.evidence_confidence && (
          <Badge tone={EVIDENCE_TONE[result.evidence_confidence]} className="px-3 py-1">
            {EVIDENCE_LABELS[result.evidence_confidence]}
          </Badge>
        )}
      </div>

      {result.evidence_confidence && (
        <p className="mt-2 text-xs text-slate-500">{EVIDENCE_NOTES[result.evidence_confidence]}</p>
      )}

      <div className="mt-4">
        <h3 className="text-sm font-semibold text-slate-700">Fit summary</h3>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{result.fit_summary}</p>
      </div>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-700">Findings</h3>
        <div className="mt-2">
          <FindingsList findings={result.findings} />
        </div>
      </div>

      <DisagreementsList disagreements={result.disagreements} />
    </Card>
  );
}

function ResumeText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Resume text</h3>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
        >
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>
      {expanded && (
        <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap font-sans text-sm text-slate-800">
          {text}
        </pre>
      )}
    </Card>
  );
}

export default function CandidateDetailPage() {
  const { candidateId } = useParams<{ candidateId: string }>();

  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useDocumentTitle(detail?.candidate.name ?? "Candidate");

  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadCandidate = useCallback(async () => {
    if (!candidateId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getCandidate(candidateId);
      setDetail(data);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load candidate.");
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    loadCandidate();
  }, [loadCandidate]);

  // Poll job status once a Stage 2 verification job has been kicked off.
  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);
        if (cancelled) return;

        if (status.status === "finished") {
          setVerifying(false);
          setJobId(null);
          if (status.result) {
            setDetail((prev) =>
              prev
                ? { ...prev, match_results: [...prev.match_results, status.result as MatchResult] }
                : prev,
            );
          } else {
            // Finished but no result attached; refetch to be safe.
            await loadCandidate();
          }
          return;
        }

        if (status.status === "failed") {
          setVerifying(false);
          setJobId(null);
          setVerifyError(status.error ?? "Verification job failed.");
          return;
        }

        // Still pending/running: schedule next poll.
        pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setVerifying(false);
        setJobId(null);
        setVerifyError(err instanceof Error ? err.message : "Failed to check verification status.");
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [jobId, loadCandidate]);

  const handleVerify = async () => {
    if (!candidateId) return;
    setVerifyError(null);
    setVerifying(true);
    try {
      const response = await verifyCandidate(candidateId);
      setJobId(response.job_id);
    } catch (err) {
      setVerifying(false);
      setVerifyError(err instanceof Error ? err.message : "Failed to start verification.");
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" /> Loading candidate…
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <ErrorBanner onRetry={loadCandidate}>{loadError}</ErrorBanner>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <p className="text-sm text-slate-500">Candidate not found.</p>
      </div>
    );
  }

  const { candidate, match_results } = detail;
  const stage1Results = match_results.filter((r) => r.stage === 1);
  const stage2Results = match_results.filter((r) => r.stage === 2);
  const hasStage2 = stage2Results.length > 0;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-10">
      <Link
        to={`/jobs/${candidate.job_description_id}`}
        className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800"
      >
        &larr; Back to job
      </Link>

      <Card className="p-5">
        <h1 className="text-xl font-bold tracking-tight text-slate-900">{candidate.name}</h1>
        <dl className="mt-2 space-y-1 text-sm text-slate-700">
          {candidate.email && (
            <div className="flex gap-2">
              <dt className="font-medium text-slate-500">Email:</dt>
              <dd>
                <a href={`mailto:${candidate.email}`} className="text-indigo-600 hover:underline">
                  {candidate.email}
                </a>
              </dd>
            </div>
          )}
          {candidate.github_url && (
            <div className="flex gap-2">
              <dt className="font-medium text-slate-500">GitHub:</dt>
              <dd>
                <a
                  href={candidate.github_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-indigo-600 hover:underline"
                >
                  {candidate.github_url}
                </a>
              </dd>
            </div>
          )}
          {candidate.website_url && (
            <div className="flex gap-2">
              <dt className="font-medium text-slate-500">Website:</dt>
              <dd>
                <a
                  href={candidate.website_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-indigo-600 hover:underline"
                >
                  {candidate.website_url}
                </a>
              </dd>
            </div>
          )}
        </dl>
      </Card>

      {candidate.resume_raw_text && <ResumeText text={candidate.resume_raw_text} />}

      <section>
        <h2 className="text-lg font-semibold text-slate-900">Stage 1 · Initial screen</h2>
        <p className="mb-3 text-sm text-slate-500">Automated first-pass assessment from the resume alone.</p>
        {stage1Results.length === 0 ? (
          <p className="text-sm italic text-slate-500">No Stage 1 result available.</p>
        ) : (
          <div className="space-y-4">
            {stage1Results.map((result) => (
              <MatchResultCard key={result.id} result={result} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">Stage 2 · Verification</h2>
        <p className="mb-3 text-sm text-slate-500">
          Deeper check against outside evidence (e.g. GitHub, portfolio) beyond the resume.
        </p>

        {stage2Results.length > 0 && (
          <div className="space-y-4">
            {stage2Results.map((result) => (
              <MatchResultCard key={result.id} result={result} />
            ))}
          </div>
        )}

        {!hasStage2 && !verifying && (
          <Card className="border-dashed p-5">
            <p className="text-sm text-slate-600">No Stage 2 verification has been run for this candidate yet.</p>
            <Button onClick={handleVerify} className="mt-3">
              Verify
            </Button>
          </Card>
        )}

        {verifying && (
          <Card className="border-dashed border-indigo-200 bg-indigo-50/60 p-5">
            <p className="flex items-center gap-2 text-sm text-indigo-800">
              <Spinner className="h-4 w-4" />
              Verification in progress. This can take a little while&hellip;
            </p>
          </Card>
        )}

        {verifyError && (
          <div className="mt-3">
            <ErrorBanner onRetry={handleVerify}>{verifyError}</ErrorBanner>
          </div>
        )}
      </section>
    </div>
  );
}
