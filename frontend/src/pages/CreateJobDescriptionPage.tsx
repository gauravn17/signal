import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createJobDescription } from "../api/client";
import { Button, Card, ErrorBanner, Spinner } from "../components/ui";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function CreateJobDescriptionPage() {
  useDocumentTitle("New job description");
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

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
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800">
        &larr; Back to home
      </Link>

      <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">New job description</h1>
      <p className="mt-1 text-sm text-slate-500">
        Paste the raw job posting text — it's parsed into structured must-have/nice-to-have
        requirements automatically, including hiring-team-specific criteria a keyword filter would miss.
      </p>

      <Card className="mt-6 p-6">
        {createError && (
          <div className="mb-4">
            <ErrorBanner>{createError}</ErrorBanner>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
              autoFocus
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
              rows={14}
              placeholder="Paste the raw job description here..."
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50"
            />
          </div>

          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={isCreating}>
              {isCreating && <Spinner className="h-4 w-4" />}
              {isCreating ? "Parsing requirements…" : "Create job description"}
            </Button>
            {isCreating && <span className="text-sm text-slate-500">This can take a few seconds.</span>}
          </div>
        </form>
      </Card>
    </div>
  );
}
