import { validateSelectorBundle } from "../selectors/validator";
import type {
  ArtifactRef,
  AttachmentBridge,
  JobPosting,
  JobSummary,
  ListingOptions,
  Platform,
  PlatformAdapter,
  PlatformPage,
  PreflightResult,
  SelectorBundle,
  SubmissionResult,
} from "./types";


function text(element: Element | null): string {
  return element?.textContent?.replace(/\s+/g, " ").trim() ?? "";
}


function parseSalary(value: string): [number | null, number | null] {
  const match = value.match(/(\d+(?:\.\d+)?)\s*(?:-|~|—|至)\s*(\d+(?:\.\d+)?)\s*[kK]/);
  if (!match) return [null, null];
  return [Number(match[1]), Number(match[2])];
}


function activityDate(value: string): string | null {
  const match = value.match(/(\d+)\s*(?:日|天)内/);
  if (!match) return null;
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - Number(match[1]));
  return date.toISOString();
}


function jobId(link: HTMLAnchorElement, platform: Platform): string {
  if (link.dataset.jobId) return link.dataset.jobId;
  const url = new URL(link.href);
  const fromQuery = url.searchParams.get("jobId") ?? url.searchParams.get("positionId");
  const pathPart = url.pathname.split("/").filter(Boolean).at(-1)?.replace(/\.html$/, "");
  return fromQuery ?? pathPart ?? `${platform}-${url.pathname}`;
}


export abstract class DomesticPlatformAdapter implements PlatformAdapter {
  protected readonly bundle: SelectorBundle;
  private stopped = false;

  protected constructor(
    protected readonly document: Document,
    protected readonly attachmentBridge: AttachmentBridge,
    bundle: SelectorBundle,
  ) {
    this.bundle = validateSelectorBundle(bundle);
  }

  protected get platform(): Exclude<Platform, "mock"> {
    return this.bundle.platform;
  }

  detectPage(): PlatformPage {
    const selectors = this.bundle.selectors;
    if (this.document.querySelector(selectors.captcha) || this.document.querySelector(selectors.riskPage)) {
      return "risk";
    }
    if (this.document.querySelector(selectors.loginRequired)) return "login";
    if (this.document.querySelector(selectors.description)) return "job_detail";
    if (this.document.querySelector(selectors.listingCard)) return "listings";
    return "unknown";
  }

  async *collectListings(options: ListingOptions): AsyncIterable<JobSummary> {
    if (this.stopped) return;
    const selectors = this.bundle.selectors;
    const cards = Array.from(this.document.querySelectorAll(selectors.listingCard)).slice(
      0,
      Math.max(0, options.limit),
    );
    for (const card of cards) {
      const link = card.querySelector<HTMLAnchorElement>(selectors.listingLink);
      if (!link) continue;
      yield {
        platform: this.platform,
        platformJobId: jobId(link, this.platform),
        url: new URL(link.getAttribute("href") ?? link.href, this.document.baseURI).href,
        title: text(card.querySelector(selectors.title)),
        company: text(card.querySelector(selectors.company)),
      };
    }
  }

  async extractJob(ref: JobSummary): Promise<JobPosting> {
    const selectors = this.bundle.selectors;
    const [salaryMinK, salaryMaxK] = parseSalary(text(this.document.querySelector(selectors.salary)));
    return {
      ...ref,
      platform: this.platform,
      description: text(this.document.querySelector(selectors.description)),
      salaryMinK,
      salaryMaxK,
      location: text(this.document.querySelector(selectors.location)),
      experience: text(this.document.querySelector(selectors.experience)),
      education: text(this.document.querySelector(selectors.education)),
      hrActiveAt: activityDate(text(this.document.querySelector(selectors.hrActivity))),
      snapshotAt: new Date().toISOString(),
    };
  }

  async preflight(_job: JobPosting, artifact: ArtifactRef): Promise<PreflightResult> {
    if (this.stopped) {
      return { ok: false, status: "risk_stopped", reasons: ["adapter_stopped"] };
    }
    const selectors = this.bundle.selectors;
    if (this.document.querySelector(selectors.captcha)) {
      return { ok: false, status: "risk_stopped", reasons: ["captcha_detected"] };
    }
    if (this.document.querySelector(selectors.riskPage)) {
      return { ok: false, status: "risk_stopped", reasons: ["platform_risk_page"] };
    }
    if (this.document.querySelector(selectors.loginRequired)) {
      return { ok: false, status: "risk_stopped", reasons: ["login_expired"] };
    }
    if (!this.document.querySelector(selectors.description)) {
      return { ok: false, status: "page_changed", reasons: ["job_detail_missing"] };
    }
    if (!/^[a-f\d]{64}$/i.test(artifact.sha256)) {
      return { ok: false, status: "risk_stopped", reasons: ["artifact_hash_invalid"] };
    }
    const artifactUrl = new URL(artifact.downloadUrl);
    if (!['127.0.0.1', 'localhost', '::1'].includes(artifactUrl.hostname)) {
      return { ok: false, status: "risk_stopped", reasons: ["artifact_not_local"] };
    }
    if (!this.document.querySelector(selectors.attachmentInput)) {
      return { ok: false, status: "requires_user_action", reasons: ["attachment_control_unavailable"] };
    }
    return { ok: true, status: "ready", reasons: [] };
  }

  async submit(
    job: JobPosting,
    artifact: ArtifactRef,
    greeting: string,
  ): Promise<SubmissionResult> {
    const preflight = await this.preflight(job, artifact);
    if (!preflight.ok) {
      if (preflight.status === "requires_user_action") {
        return {
          status: "requires_user_action",
          artifactPath: artifact.path,
          reason: preflight.reasons.join(","),
        };
      }
      return { status: "risk_stopped", reason: preflight.reasons.join(",") };
    }

    const selectors = this.bundle.selectors;
    if (selectors.contactButton) {
      this.document.querySelector<HTMLElement>(selectors.contactButton)?.click();
    }
    const attachmentInput = this.document.querySelector<HTMLInputElement>(selectors.attachmentInput);
    if (!attachmentInput || !(await this.attachmentBridge.attach(attachmentInput, artifact))) {
      return {
        status: "requires_user_action",
        artifactPath: artifact.path,
        reason: "attachment_automation_blocked",
      };
    }
    const greetingInput = this.document.querySelector<HTMLInputElement | HTMLTextAreaElement>(
      selectors.greetingInput,
    );
    const submitButton = this.document.querySelector<HTMLElement>(selectors.submitButton);
    if (!greetingInput || !submitButton) {
      return { status: "requires_user_action", artifactPath: artifact.path, reason: "composer_missing" };
    }
    greetingInput.value = greeting.slice(0, 500);
    greetingInput.dispatchEvent(new Event("input", { bubbles: true }));
    submitButton.click();

    const risk = await this.preflight(job, artifact);
    if (risk.status === "risk_stopped") {
      return { status: "risk_stopped", reason: risk.reasons.join(",") };
    }
    const success = this.document.querySelector<HTMLElement>(selectors.successMarker);
    if (success) {
      const remoteId = success.dataset.remoteId;
      return remoteId ? { status: "submitted", remoteId } : { status: "submitted" };
    }
    return { status: "submitting" };
  }

  async observeResult(_taskId: string): Promise<SubmissionResult> {
    const selectors = this.bundle.selectors;
    if (this.document.querySelector(selectors.captcha) || this.document.querySelector(selectors.riskPage)) {
      return { status: "risk_stopped", reason: "risk_detected_while_observing" };
    }
    const success = this.document.querySelector<HTMLElement>(selectors.successMarker);
    if (!success) return { status: "unknown" };
    const remoteId = success.dataset.remoteId;
    return remoteId ? { status: "submitted", remoteId } : { status: "submitted" };
  }

  async stop(): Promise<void> {
    this.stopped = true;
  }
}

