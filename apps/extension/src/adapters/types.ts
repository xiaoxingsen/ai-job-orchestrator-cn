import type {
  ArtifactRef,
  JobPosting,
  JobSummary,
  Platform,
  PlatformPage,
} from "@job-orchestrator/contracts";

export type { ArtifactRef, JobPosting, JobSummary, Platform, PlatformPage };

export interface ListingOptions {
  limit: number;
}

export interface PreflightResult {
  ok: boolean;
  status: "ready" | "requires_user_action" | "risk_stopped" | "page_changed";
  reasons: string[];
}

export interface SubmissionResult {
  status:
    | "submitting"
    | "submitted"
    | "requires_user_action"
    | "risk_stopped"
    | "failed"
    | "unknown";
  remoteId?: string;
  artifactPath?: string;
  reason?: string;
}

export interface AttachmentBridge {
  attach(input: HTMLInputElement, artifact: ArtifactRef): Promise<boolean>;
}

export interface SelectorMap {
  listingCard: string;
  listingLink: string;
  title: string;
  company: string;
  description: string;
  salary: string;
  location: string;
  experience: string;
  education: string;
  hrActivity: string;
  captcha: string;
  riskPage: string;
  loginRequired: string;
  greetingInput: string;
  submitButton: string;
  attachmentInput: string;
  successMarker: string;
  contactButton?: string;
}

export interface SelectorBundle {
  schemaVersion: 1;
  selectorVersion: string;
  platform: Exclude<Platform, "mock">;
  selectors: SelectorMap;
}

export interface PlatformAdapter {
  detectPage(): PlatformPage;
  collectListings(options: ListingOptions): AsyncIterable<JobSummary>;
  extractJob(ref: JobSummary): Promise<JobPosting>;
  preflight(job: JobPosting, artifact: ArtifactRef): Promise<PreflightResult>;
  submit(job: JobPosting, artifact: ArtifactRef, greeting: string): Promise<SubmissionResult>;
  observeResult(taskId: string): Promise<SubmissionResult>;
  stop(): Promise<void>;
}

