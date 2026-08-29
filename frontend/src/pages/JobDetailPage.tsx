import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  createCandidate,
  getJobDescription,
  listCandidates,
  shortlistCandidates,
} from "../api/client";
import type { Candidate, JobDescription, RequirementItem } from "../api/types";
import { Badge, Button, Card, ErrorBanner, SuccessBanner, Spinner } from "../components/ui";

const SOURCE_LABELS: Record<RequirementItem["source"], string> = {
  generic: "Generic",
  hiring_team_free_text: "Hiring team",
};

function RequirementList({ items }: { items: RequirementItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm italic text-slate-400">None listed</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((item, idx) => (
        <li key={idx} className="flex flex-wrap items-start gap-2 text-sm text-slate-700">
          <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
          <span className="flex-1">{item.text}</span>
          <Badge tone={item.source === "hiring_team_free_text" ? "primary" : "neutral"}>
            {SOURCE_LABELS[item.source]}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

interface UploadFormState {
  name: string;
  email: string;
  githubUrl: string;
  websiteUrl: string;
}

const EMPTY_FORM: UploadFormState = {
  name: "",
  email: "",
  githubUrl: "",
  websiteUrl: "",
};

interface UploadOutcome {
  fileName: string;
  ok: boolean;
  message: string;
}

export default function JobDetailPage() {
  const { jdId } = useParams<{ jdId: string }>();

  const [jd, setJd] = useState<JobDescription | null>(null);
  const [jdLoading, setJdLoading] = useState(true);
  const [jdError, setJdError] = useState<string | null>(null);
  const [rawTextExpanded, setRawTextExpanded] = useState(false);

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(true);
  const [candidatesError, setCandidatesError] = useState<string | null>(null);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [shortlistSubmitting, setShortlistSubmitting] = useState(false);
  const [shortlistError, setShortlistError] = useState<string | null>(null);
  const [shortlistMessage, setShortlistMessage] = useState<string | null>(null);

  const [form, setForm] = useState<UploadFormState>(EMPTY_FORM);
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadOutcomes, setUploadOutcomes] = useState<UploadOutcome[]>([]);

  // Manual name/email/github/website only make sense for a single resume —
  // for a batch, every candidate's contact info is auto-extracted instead.
  const isBatch = resumeFiles.length > 1;

  const loadJobDescription = useCallback(async () => {
    if (!jdId) return;
    setJdLoading(true);
    setJdError(null);
    try {
      const data = await getJobDescription(jdId);
      setJd(data);
    } catch (err) {
      setJdError(err instanceof Error ? err.message : "Failed to load job description.");
    } finally {
      setJdLoading(false);
    }
  }, [jdId]);

  const loadCandidates = useCallback(async () => {
    if (!jdId) return;
    setCandidatesLoading(true);
    setCandidatesError(null);
    try {
      const data = await listCandidates(jdId);
      setCandidates(data);
    } catch (err) {
      setCandidatesError(err instanceof Error ? err.message : "Failed to load candidates.");
    } finally {
      setCandidatesLoading(false);
    }
  }, [jdId]);

  useEffect(() => {
    void loadJobDescription();
    void loadCandidates();
  }, [loadJobDescription, loadCandidates]);

  const mustHave = useMemo(
    () => jd?.requirements.filter((r) => r.category === "must_have") ?? [],
    [jd],
  );
  const niceToHave = useMemo(
    () => jd?.requirements.filter((r) => r.category === "nice_to_have") ?? [],
    [jd],
  );

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) =>
      prev.size === candidates.length ? new Set() : new Set(candidates.map((c) => c.id)),
    );
  }

  async function handleVerifySelected() {
    if (!jdId || selectedIds.size === 0) return;
    setShortlistSubmitting(true);
    setShortlistError(null);
    setShortlistMessage(null);
    try {
      const jobs = await shortlistCandidates(jdId, Array.from(selectedIds));
      setShortlistMessage(
        `${jobs.length} verification job${jobs.length === 1 ? "" : "s"} queued. Results will appear on each candidate's page once processing finishes.`,
      );
      setSelectedIds(new Set());
    } catch (err) {
      setShortlistError(err instanceof Error ? err.message : "Failed to queue verification jobs.");
    } finally {
      setShortlistSubmitting(false);
    }
  }

  async function handleUploadSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!jdId) return;
    if (resumeFiles.length === 0) {
      setUploadError("At least one resume file is required.");
      return;
    }

    setUploadSubmitting(true);
    setUploadError(null);
    setUploadOutcomes([]);
    setUploadProgress({ done: 0, total: resumeFiles.length });

    const outcomes: UploadOutcome[] = [];
    for (const file of resumeFiles) {
      try {
        const formData = new FormData();
        formData.append("job_description_id", jdId);
        // Manual overrides only apply to a single-file upload — for a batch,
        // every candidate's name/email/links come from their own resume.
        if (!isBatch) {
          if (form.name.trim()) formData.append("name", form.name.trim());
          if (form.email.trim()) formData.append("email", form.email.trim());
          if (form.githubUrl.trim()) formData.append("github_url", form.githubUrl.trim());
          if (form.websiteUrl.trim()) formData.append("website_url", form.websiteUrl.trim());
        }
        formData.append("resume", file);

        const result = await createCandidate(formData);
        outcomes.push({ fileName: file.name, ok: true, message: `Added ${result.candidate.name}.` });
      } catch (err) {
        outcomes.push({
          fileName: file.name,
          ok: false,
          message: err instanceof Error ? err.message : "Upload failed.",
        });
      }
      setUploadProgress({ done: outcomes.length, total: resumeFiles.length });
    }

    setUploadOutcomes(outcomes);
    setForm(EMPTY_FORM);
    setResumeFiles([]);
    const fileInput = document.getElementById("resume-file-input") as HTMLInputElement | null;
    if (fileInput) fileInput.value = "";
    setUploadSubmitting(false);
    setUploadProgress(null);
    await loadCandidates();
  }

  if (!jdId) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10">
        <ErrorBanner>Missing job description id in URL.</ErrorBanner>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800">
        &larr; Back to job descriptions
      </Link>

      {/* Job description */}
      <section className="space-y-4">
        {jdLoading && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading job description…
          </div>
        )}
        {jdError && <ErrorBanner>{jdError}</ErrorBanner>}
        {jd && (
          <>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{jd.title}</h1>
              <p className="mt-1 text-xs text-slate-400">Created {new Date(jd.created_at).toLocaleString()}</p>
            </div>

            <Card className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">Raw text</h2>
                <button
                  type="button"
                  onClick={() => setRawTextExpanded((v) => !v)}
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                >
                  {rawTextExpanded ? "Collapse" : "Expand"}
                </button>
              </div>
              <p
                className={`mt-2 whitespace-pre-wrap text-sm text-slate-600 ${
                  rawTextExpanded ? "" : "line-clamp-3 overflow-hidden"
                }`}
              >
                {jd.raw_text}
              </p>
            </Card>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Card className="p-5">
                <h2 className="mb-3 text-sm font-semibold text-slate-700">Must-have requirements</h2>
                <RequirementList items={mustHave} />
              </Card>
              <Card className="p-5">
                <h2 className="mb-3 text-sm font-semibold text-slate-700">Nice-to-have requirements</h2>
                <RequirementList items={niceToHave} />
              </Card>
            </div>
          </>
        )}
      </section>

      {/* Resume upload */}
      <Card className="space-y-4 p-6">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Upload resumes</h2>
          <p className="mt-1 text-sm text-slate-500">
            Select one or more resumes. Name, email, GitHub, and website are read straight off each
            resume — you don't need to type them in.
          </p>
        </div>
        <form onSubmit={handleUploadSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="resume-file-input">
              Resume file(s) *
            </label>
            <input
              id="resume-file-input"
              type="file"
              multiple
              required
              onChange={(e) => setResumeFiles(Array.from(e.target.files ?? []))}
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
            />
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-slate-600">
              Optional overrides{isBatch ? " (only apply to a single-file upload)" : ""}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-slate-500" htmlFor="candidate-name">
                  Name
                </label>
                <input
                  id="candidate-name"
                  type="text"
                  disabled={isBatch}
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-500" htmlFor="candidate-email">
                  Email
                </label>
                <input
                  id="candidate-email"
                  type="email"
                  disabled={isBatch}
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-500" htmlFor="candidate-github">
                  GitHub URL
                </label>
                <input
                  id="candidate-github"
                  type="url"
                  disabled={isBatch}
                  value={form.githubUrl}
                  onChange={(e) => setForm((f) => ({ ...f, githubUrl: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-500" htmlFor="candidate-website">
                  Website URL
                </label>
                <input
                  id="candidate-website"
                  type="url"
                  disabled={isBatch}
                  value={form.websiteUrl}
                  onChange={(e) => setForm((f) => ({ ...f, websiteUrl: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>
            </div>
          </div>

          {uploadError && <ErrorBanner>{uploadError}</ErrorBanner>}
          {uploadOutcomes.length > 0 && (
            <div className="space-y-1.5">
              {uploadOutcomes.map((o, idx) =>
                o.ok ? (
                  <SuccessBanner key={idx}>
                    <span className="font-medium">{o.fileName}:</span> {o.message}
                  </SuccessBanner>
                ) : (
                  <ErrorBanner key={idx}>
                    <span className="font-medium">{o.fileName}:</span> {o.message}
                  </ErrorBanner>
                ),
              )}
            </div>
          )}

          <Button type="submit" disabled={uploadSubmitting || resumeFiles.length === 0}>
            {uploadSubmitting && <Spinner className="h-4 w-4" />}
            {uploadSubmitting
              ? `Running Stage 1 match… (${uploadProgress?.done ?? 0}/${uploadProgress?.total ?? resumeFiles.length})`
              : `Upload ${resumeFiles.length || ""} resume${resumeFiles.length === 1 ? "" : "s"}`.trim()}
          </Button>
        </form>
      </Card>

      {/* Candidates table */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Candidates</h2>
          <Button
            variant="secondary"
            onClick={handleVerifySelected}
            disabled={selectedIds.size === 0 || shortlistSubmitting}
            className="border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
          >
            {shortlistSubmitting && <Spinner className="h-4 w-4" />}
            {shortlistSubmitting
              ? "Queuing…"
              : `Verify Selected${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </Button>
        </div>

        {shortlistError && <ErrorBanner>{shortlistError}</ErrorBanner>}
        {shortlistMessage && <SuccessBanner>{shortlistMessage}</SuccessBanner>}

        {candidatesLoading && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading candidates…
          </div>
        )}
        {candidatesError && <ErrorBanner>{candidatesError}</ErrorBanner>}

        {!candidatesLoading && !candidatesError && candidates.length === 0 && (
          <Card className="px-6 py-10 text-center">
            <p className="text-sm text-slate-500">No candidates yet for this job. Upload resumes above.</p>
          </Card>
        )}

        {!candidatesLoading && !candidatesError && candidates.length > 0 && (
          <Card className="overflow-hidden">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="w-10 px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === candidates.length && candidates.length > 0}
                      onChange={toggleSelectAll}
                      aria-label="Select all candidates"
                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Links
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Added
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {candidates.map((c) => (
                  <tr key={c.id} className="transition hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelected(c.id)}
                        aria-label={`Select ${c.name}`}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/candidates/${c.id}`} className="font-medium text-indigo-600 hover:text-indigo-800">
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{c.email ?? "—"}</td>
                    <td className="space-x-3 px-4 py-3">
                      {c.github_url && (
                        <a
                          href={c.github_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-600 hover:text-indigo-800"
                        >
                          GitHub
                        </a>
                      )}
                      {c.website_url && (
                        <a
                          href={c.website_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-600 hover:text-indigo-800"
                        >
                          Website
                        </a>
                      )}
                      {!c.github_url && !c.website_url && <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{new Date(c.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </section>
    </div>
  );
}
