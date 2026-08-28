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

const SOURCE_LABELS: Record<RequirementItem["source"], string> = {
  generic: "Generic",
  hiring_team_free_text: "Hiring team",
};

function RequirementBadge({ source }: { source: RequirementItem["source"] }) {
  const isHiringTeam = source === "hiring_team_free_text";
  return (
    <span
      className={`ml-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        isHiringTeam
          ? "bg-purple-100 text-purple-700"
          : "bg-gray-100 text-gray-600"
      }`}
    >
      {SOURCE_LABELS[source]}
    </span>
  );
}

function RequirementList({ items }: { items: RequirementItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-400 italic">None listed</p>;
  }
  return (
    <ul className="space-y-1.5">
      {items.map((item, idx) => (
        <li key={idx} className="text-sm text-gray-800 flex items-start flex-wrap">
          <span>{item.text}</span>
          <RequirementBadge source={item.source} />
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
    return <div className="p-6 text-red-600">Missing job description id in URL.</div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      <div>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          &larr; Back to job descriptions
        </Link>
      </div>

      {/* Job description */}
      <section className="space-y-4">
        {jdLoading && <p className="text-sm text-gray-500">Loading job description…</p>}
        {jdError && (
          <div className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {jdError}
          </div>
        )}
        {jd && (
          <>
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">{jd.title}</h1>
              <p className="text-xs text-gray-400 mt-1">
                Created {new Date(jd.created_at).toLocaleString()}
              </p>
            </div>

            <div className="rounded border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-700">Raw text</h2>
                <button
                  type="button"
                  onClick={() => setRawTextExpanded((v) => !v)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {rawTextExpanded ? "Collapse" : "Expand"}
                </button>
              </div>
              <p
                className={`mt-2 whitespace-pre-wrap text-sm text-gray-700 ${
                  rawTextExpanded ? "" : "line-clamp-3 overflow-hidden"
                }`}
              >
                {jd.raw_text}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded border border-gray-200 bg-white p-4">
                <h2 className="text-sm font-medium text-gray-700 mb-2">Must-have requirements</h2>
                <RequirementList items={mustHave} />
              </div>
              <div className="rounded border border-gray-200 bg-white p-4">
                <h2 className="text-sm font-medium text-gray-700 mb-2">Nice-to-have requirements</h2>
                <RequirementList items={niceToHave} />
              </div>
            </div>
          </>
        )}
      </section>

      {/* Resume upload */}
      <section className="rounded border border-gray-200 bg-white p-4 space-y-3">
        <h2 className="text-lg font-medium text-gray-900">Upload resumes</h2>
        <p className="text-xs text-gray-500">
          Select one or more resumes. Name, email, GitHub, and website are read straight off
          each resume — you don't need to type them in.
        </p>
        <form onSubmit={handleUploadSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1" htmlFor="resume-file-input">
              Resume file(s) *
            </label>
            <input
              id="resume-file-input"
              type="file"
              multiple
              required
              onChange={(e) => setResumeFiles(Array.from(e.target.files ?? []))}
              className="block w-full text-sm text-gray-600 file:mr-3 file:rounded file:border-0 file:bg-gray-100 file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-gray-200"
            />
          </div>

          <div>
            <p className="text-xs font-medium text-gray-600 mb-1">
              Optional overrides{isBatch ? " (only apply to a single-file upload)" : ""}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="candidate-name">
                  Name
                </label>
                <input
                  id="candidate-name"
                  type="text"
                  disabled={isBatch}
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="candidate-email">
                  Email
                </label>
                <input
                  id="candidate-email"
                  type="email"
                  disabled={isBatch}
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="candidate-github">
                  GitHub URL
                </label>
                <input
                  id="candidate-github"
                  type="url"
                  disabled={isBatch}
                  value={form.githubUrl}
                  onChange={(e) => setForm((f) => ({ ...f, githubUrl: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="candidate-website">
                  Website URL
                </label>
                <input
                  id="candidate-website"
                  type="url"
                  disabled={isBatch}
                  value={form.websiteUrl}
                  onChange={(e) => setForm((f) => ({ ...f, websiteUrl: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>
            </div>
          </div>

          {uploadError && (
            <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
              {uploadError}
            </div>
          )}
          {uploadOutcomes.length > 0 && (
            <div className="space-y-1">
              {uploadOutcomes.map((o, idx) => (
                <div
                  key={idx}
                  className={`rounded border px-3 py-2 text-sm ${
                    o.ok
                      ? "border-green-300 bg-green-50 text-green-700"
                      : "border-red-300 bg-red-50 text-red-700"
                  }`}
                >
                  <span className="font-medium">{o.fileName}:</span> {o.message}
                </div>
              ))}
            </div>
          )}

          <button
            type="submit"
            disabled={uploadSubmitting || resumeFiles.length === 0}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploadSubmitting
              ? `Running Stage 1 match… (${uploadProgress?.done ?? 0}/${uploadProgress?.total ?? resumeFiles.length})`
              : `Upload ${resumeFiles.length || ""} resume${resumeFiles.length === 1 ? "" : "s"}`.trim()}
          </button>
        </form>
      </section>

      {/* Candidates table */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-900">Candidates</h2>
          <button
            type="button"
            onClick={handleVerifySelected}
            disabled={selectedIds.size === 0 || shortlistSubmitting}
            className="rounded bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {shortlistSubmitting
              ? "Queuing…"
              : `Verify Selected${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>
        </div>

        {shortlistError && (
          <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {shortlistError}
          </div>
        )}
        {shortlistMessage && (
          <div className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-700">
            {shortlistMessage}
          </div>
        )}

        {candidatesLoading && <p className="text-sm text-gray-500">Loading candidates…</p>}
        {candidatesError && (
          <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {candidatesError}
          </div>
        )}

        {!candidatesLoading && !candidatesError && candidates.length === 0 && (
          <p className="text-sm text-gray-400 italic">No candidates yet for this job.</p>
        )}

        {!candidatesLoading && !candidatesError && candidates.length > 0 && (
          <div className="overflow-x-auto rounded border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="w-10 px-3 py-2 text-left">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === candidates.length && candidates.length > 0}
                      onChange={toggleSelectAll}
                      aria-label="Select all candidates"
                    />
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">Email</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">Links</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {candidates.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelected(c.id)}
                        aria-label={`Select ${c.name}`}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <Link
                        to={`/candidates/${c.id}`}
                        className="font-medium text-blue-600 hover:underline"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-gray-700">{c.email ?? "—"}</td>
                    <td className="px-3 py-2 space-x-2">
                      {c.github_url && (
                        <a
                          href={c.github_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          GitHub
                        </a>
                      )}
                      {c.website_url && (
                        <a
                          href={c.website_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          Website
                        </a>
                      )}
                      {!c.github_url && !c.website_url && <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
