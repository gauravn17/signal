import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, listJobDescriptions } from "../api/client";
import type { JobDescription, Stats } from "../api/types";
import { Badge, Button, Card, ErrorBanner, Spinner } from "../components/ui";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

function StatCard({ label, value }: { label: string; value: number | null }) {
  return (
    <Card className="p-5">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
        {value === null ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-slate-200" /> : value}
      </p>
    </Card>
  );
}

export default function HomePage() {
  useDocumentTitle("Home");

  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [jobDescriptions, setJobDescriptions] = useState<JobDescription[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getStats()
      .then((data) => !cancelled && setStats(data))
      .catch((err: unknown) => !cancelled && setStatsError(err instanceof Error ? err.message : "Failed to load stats."));

    setListLoading(true);
    setListError(null);
    listJobDescriptions()
      .then((data) => !cancelled && setJobDescriptions(data))
      .catch((err: unknown) => !cancelled && setListError(err instanceof Error ? err.message : "Failed to load job descriptions."))
      .finally(() => !cancelled && setListLoading(false));

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Welcome back</h1>
        <p className="mt-2 max-w-2xl text-base text-slate-600">
          Signal turns an unscreenable applicant pool into a shortlist a hiring manager can actually
          read and trust — with evidence and reasoning surfaced, not a black-box score.
        </p>
      </div>

      {/* Stats */}
      {statsError && (
        <div className="mb-6">
          <ErrorBanner>{statsError}</ErrorBanner>
        </div>
      )}
      <div className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Job descriptions" value={stats?.job_description_count ?? null} />
        <StatCard label="Candidates reviewed" value={stats?.candidate_count ?? null} />
        <StatCard label="Stage 2 verifications" value={stats?.stage2_verified_count ?? null} />
      </div>

      {/* Job descriptions */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Job descriptions</h2>
        <Link to="/jobs/new">
          <Button>New job description</Button>
        </Link>
      </div>

      {listError && <ErrorBanner>{listError}</ErrorBanner>}

      {listLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" /> Loading job descriptions…
        </div>
      )}

      {!listLoading && !listError && jobDescriptions.length === 0 && (
        <Card className="px-6 py-12 text-center">
          <p className="text-sm text-slate-500">No job descriptions yet.</p>
          <Link to="/jobs/new" className="mt-4 inline-block">
            <Button>Create your first job description</Button>
          </Link>
        </Card>
      )}

      {!listLoading && jobDescriptions.length > 0 && (
        <div className="flex flex-col gap-3">
          {jobDescriptions.map((jd) => (
            <Link key={jd.id} to={`/jobs/${jd.id}`}>
              <Card className="px-5 py-4 transition hover:border-indigo-300 hover:shadow-md">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-slate-900">{jd.title}</span>
                  <span className="shrink-0 text-xs text-slate-400">{formatDate(jd.created_at)}</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge tone="primary">
                    {jd.requirements.length} requirement{jd.requirements.length === 1 ? "" : "s"}
                  </Badge>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return isoString;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
