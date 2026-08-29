import type {
  Candidate,
  CandidateDetail,
  CandidateWithMatch,
  JobDescription,
  JobStatusResponse,
  Stats,
  VerifyJobResponse,
} from "./types";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function listJobDescriptions(): Promise<JobDescription[]> {
  return request<JobDescription[]>("/job-descriptions");
}

export function createJobDescription(title: string, raw_text: string): Promise<JobDescription> {
  return request<JobDescription>("/job-descriptions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, raw_text }),
  });
}

export function getJobDescription(id: string): Promise<JobDescription> {
  return request<JobDescription>(`/job-descriptions/${id}`);
}

export function shortlistCandidates(
  jdId: string,
  candidateIds: string[],
): Promise<VerifyJobResponse[]> {
  return request<VerifyJobResponse[]>(`/job-descriptions/${jdId}/shortlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
}

export function listCandidates(jdId: string): Promise<Candidate[]> {
  const params = new URLSearchParams({ job_description_id: jdId });
  return request<Candidate[]>(`/candidates?${params.toString()}`);
}

export function createCandidate(formData: FormData): Promise<CandidateWithMatch> {
  return request<CandidateWithMatch>("/candidates", {
    method: "POST",
    body: formData,
  });
}

export function getCandidate(id: string): Promise<CandidateDetail> {
  return request<CandidateDetail>(`/candidates/${id}`);
}

export function verifyCandidate(id: string): Promise<VerifyJobResponse> {
  return request<VerifyJobResponse>(`/candidates/${id}/verify`, {
    method: "POST",
  });
}

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/jobs/${jobId}`);
}

export function getStats(): Promise<Stats> {
  return request<Stats>("/stats");
}
