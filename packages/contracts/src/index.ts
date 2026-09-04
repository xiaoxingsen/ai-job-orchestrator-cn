export type Platform = "boss" | "liepin" | "zhilian" | "mock";

export type PlatformPage =
  | "listings"
  | "job_detail"
  | "chat"
  | "login"
  | "risk"
  | "unknown";

export type AutomationMode = "confirm_before_apply" | "auto_apply" | "prepare_only";

export interface JobSummary {
  platform: Platform;
  platformJobId: string;
  url: string;
  title: string;
  company: string;
}

export interface JobPosting extends JobSummary {
  description: string;
  salaryMinK: number | null;
  salaryMaxK: number | null;
  location: string;
  experience: string;
  education: string;
  hrActiveAt: string | null;
  snapshotAt: string;
}

export interface ApprovedClaim {
  id: string;
  category: string;
  statement: string;
  evidence: string;
}

export type ResumeProposalKind = "safe_rewrite" | "pending_claim" | "gap_warning";

export interface ResumeProposal {
  id: string;
  kind: ResumeProposalKind;
  targetSection: string;
  proposedText: string;
  sourceClaimIds: string[];
  status: "pending" | "approved_current_job" | "approved_fact_library" | "rejected";
}

export interface ResumeVersion {
  id: string;
  jobId: string;
  version: number;
  template: string;
  sourceClaimIds: string[];
}

export interface ArtifactRef {
  name: string;
  path: string;
  sha256: string;
  downloadUrl: string;
  mimeType: "application/pdf" | "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
}

export type ApplicationStatus =
  | "queued"
  | "preparing"
  | "ready_for_confirmation"
  | "prepared"
  | "submitting"
  | "submitted"
  | "requires_user_action"
  | "failed"
  | "risk_stopped";

export interface ApplicationTask {
  id: string;
  jobId: string;
  resumeVersionId: string;
  greeting: string;
  mode: AutomationMode;
  platform: Platform;
  status: ApplicationStatus;
}

