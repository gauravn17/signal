import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createJobDescription, listJobDescriptions } from "../api/client";
import type { JobDescription } from "../api/types";
import { Badge, Button, Card, ErrorBanner, PageHeader, Spinner } from "../components/ui";

export default function JobDescriptionsPage() {
  const navigate = useNavigate();

  const [jobDescriptions, setJobDescriptions] = useState<JobDescription[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setIsLoadingList(true);
    setListError(null);

    listJobDescriptions()
      .then((data) => {
        if (!cancelled) {
          setJobDescriptions(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setListError(err instanceof Error ? err.message : "Failed to load job descriptions.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingList(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);

    if (!title.trim() || !rawText.trim()) {
      setCreateError("Please provide both a title and the job description text.");
      return;
    }

    setIsCreating(true);
    try {
      const created = await createJobDescription(title.trim(), rawText);
      navigate(`/jobs/${created.id}`);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to create job description.");
      setIsCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <PageHeader
        title="Job descriptions"
        description="Create a role, then review candidates against its parsed requirements."
      />

      <Card className="p-6">
        <h2 className="text-base font-semibold text-slate-900">New job description</h2>

        {createError && (
          <div className="mt-4">
            <ErrorBanner>{createError}</ErrorBanner>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div>
            <label htmlFor="jd-title" className="block text-sm font-medium text-slate-700">
              Title
            </label>
            <input
              id="jd-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isCreating}
              placeholder="e.g. Senior Backend Engineer"
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50"
            />
          </div>

          <div>
            <label htmlFor="jd-raw-text" className="block text-sm font-medium text-slate-700">
              Job description text
            </label>
            <textarea
              id="jd-raw-text"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              disabled={isCreating}
              rows={10}
              placeholder="Paste the raw job description here..."
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50"
            />
          </div>

          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={isCreating}>
              {isCreating && <Spinner className="h-4 w-4" />}
              {isCreating ? "Parsing requirements…" : "Create job description"}
            </Button>
            {isCreating && (
              <span className="text-sm text-slate-500">This can take a few seconds.</span>
            )}
          </div>
        </form>
      </Card>

      <div className="mt-10">
        <h2 className="mb-4 text-base font-semibold text-slate-900">All job descriptions</h2>

        {listError && <ErrorBanner>{listError}</ErrorBanner>}

        {isLoadingList && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading job descriptions…
          </div>
        )}

        {!isLoadingList && !listError && jobDescriptions.length === 0 && (
          <Card className="px-6 py-10 text-center">
            <p className="text-sm text-slate-500">No job descriptions yet. Create one above to get started.</p>
          </Card>
        )}

        {!isLoadingList && jobDescriptions.length > 0 && (
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
