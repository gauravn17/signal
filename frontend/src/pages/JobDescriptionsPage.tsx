import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createJobDescription, listJobDescriptions } from "../api/client";
import type { JobDescription } from "../api/types";

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
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-gray-900">Job Descriptions</h1>

      <section className="mt-6 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">New job description</h2>

        {createError && (
          <div
            role="alert"
            className="mt-4 flex items-start justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>{createError}</span>
            <button
              type="button"
              onClick={() => setCreateError(null)}
              className="shrink-0 font-medium text-red-700 hover:text-red-900"
              aria-label="Dismiss error"
            >
              &times;
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div>
            <label htmlFor="jd-title" className="block text-sm font-medium text-gray-700">
              Title
            </label>
            <input
              id="jd-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isCreating}
              placeholder="e.g. Senior Backend Engineer"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500 disabled:bg-gray-100"
            />
          </div>

          <div>
            <label htmlFor="jd-raw-text" className="block text-sm font-medium text-gray-700">
              Job description text
            </label>
            <textarea
              id="jd-raw-text"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              disabled={isCreating}
              rows={12}
              placeholder="Paste the raw job description here..."
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500 disabled:bg-gray-100"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isCreating}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-400"
            >
              {isCreating ? "Parsing job description..." : "Create job description"}
            </button>
            {isCreating && (
              <span className="text-sm text-gray-500">
                This can take a few seconds while the requirements are parsed.
              </span>
            )}
          </div>
        </form>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-gray-900">All job descriptions</h2>

        {listError && (
          <div
            role="alert"
            className="mt-4 flex items-start justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>{listError}</span>
            <button
              type="button"
              onClick={() => setListError(null)}
              className="shrink-0 font-medium text-red-700 hover:text-red-900"
              aria-label="Dismiss error"
            >
              &times;
            </button>
          </div>
        )}

        {isLoadingList && <p className="mt-4 text-sm text-gray-500">Loading job descriptions...</p>}

        {!isLoadingList && !listError && jobDescriptions.length === 0 && (
          <p className="mt-4 text-sm text-gray-500">No job descriptions yet. Create one above.</p>
        )}

        {!isLoadingList && jobDescriptions.length > 0 && (
          <ul className="mt-4 flex flex-col gap-3">
            {jobDescriptions.map((jd) => (
              <li key={jd.id}>
                <Link
                  to={`/jobs/${jd.id}`}
                  className="block rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm transition hover:border-gray-400 hover:shadow-md"
                >
                  <div className="flex items-center justify-between gap-4">
                    <span className="font-medium text-gray-900">{jd.title}</span>
                    <span className="shrink-0 text-xs text-gray-500">
                      {formatDate(jd.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-500">
                    {jd.requirements.length} parsed requirement
                    {jd.requirements.length === 1 ? "" : "s"}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
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
