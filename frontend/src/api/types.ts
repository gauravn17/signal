// Types mirroring the Signal FastAPI backend's Pydantic/SQLModel models.
// UUID and datetime fields are represented as strings (ISO 8601) over JSON.

export type RequirementCategory = "must_have" | "nice_to_have";
export type RequirementSource = "generic" | "hiring_team_free_text";
export type RequirementType = "experience" | "skill" | "leadership" | "education" | "certification" | "other";

export interface RequirementItem {
  text: string;
  category: RequirementCategory;
  source: RequirementSource;
  requirement_type: RequirementType;
}

export interface JobDescription {
  id: string;
  title: string;
  raw_text: string;
  requirements: RequirementItem[];
  created_at: string;
}

export interface Candidate {
  id: string;
  job_description_id: string;
  name: string;
  email: string | null;
  resume_raw_text: string;
  github_url: string | null;
  website_url: string | null;
  // Fields extracted from the resume in Stage 1, e.g. years_experience, skills, employment_history
  extracted_fields: Record<string, unknown>;
  created_at: string;
}

// PipelineStage: 1 = stage1_bulk, 2 = stage2_verification
export type PipelineStage = 1 | 2;

export type EvidenceConfidence = "thin" | "moderate" | "strong";

export interface MatchResult {
  id: string;
  candidate_id: string;
  job_description_id: string;
  stage: PipelineStage;
  fit_summary: string;
  evidence_confidence: EvidenceConfidence | null;
  findings: Record<string, unknown>[];
  disagreements: Record<string, unknown>[];
  // Stage 1 only: {"strengths": string[], "gaps": string[]}. Null for Stage 2
  // and for any MatchResult created before this field existed.
  assessment_details: { strengths?: string[]; gaps?: string[] } | null;
  created_at: string;
}

export interface CandidateWithMatch {
  candidate: Candidate;
  match_result: MatchResult;
}

export interface CandidateDetail {
  candidate: Candidate;
  match_results: MatchResult[];
}

export interface VerifyJobResponse {
  job_id: string;
  status: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  result: MatchResult | null;
  error: string | null;
}

export interface Stats {
  job_description_count: number;
  candidate_count: number;
  stage2_verified_count: number;
}
