import type {
  ArtifactRef,
  JobPosting,
  JobSummary,
  ListingOptions,
  PlatformAdapter,
  PlatformPage,
  PreflightResult,
  SubmissionResult,
} from "./types";


export class MockAdapter implements PlatformAdapter {
  private stopped = false;
  private readonly submitted = new Set<string>();

  constructor(private readonly jobs: JobPosting[]) {}

  detectPage(): PlatformPage {
    return this.stopped ? "risk" : "listings";
  }

  async *collectListings(options: ListingOptions): AsyncIterable<JobSummary> {
    for (const job of this.jobs.slice(0, options.limit)) yield job;
  }

  async extractJob(ref: JobSummary): Promise<JobPosting> {
    const job = this.jobs.find((item) => item.platformJobId === ref.platformJobId);
    if (!job) throw new Error("mock job not found");
    return job;
  }

  async preflight(_job: JobPosting, _artifact: ArtifactRef): Promise<PreflightResult> {
    return this.stopped
      ? { ok: false, status: "risk_stopped", reasons: ["adapter_stopped"] }
      : { ok: true, status: "ready", reasons: [] };
  }

  async submit(
    job: JobPosting,
    _artifact: ArtifactRef,
    _greeting: string,
  ): Promise<SubmissionResult> {
    if (this.stopped) return { status: "risk_stopped", reason: "adapter_stopped" };
    this.submitted.add(job.platformJobId);
    return { status: "submitted", remoteId: `mock-${job.platformJobId}` };
  }

  async observeResult(taskId: string): Promise<SubmissionResult> {
    return this.submitted.has(taskId)
      ? { status: "submitted", remoteId: `mock-${taskId}` }
      : { status: "unknown" };
  }

  async stop(): Promise<void> {
    this.stopped = true;
  }
}

