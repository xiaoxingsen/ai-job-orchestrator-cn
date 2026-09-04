import type { ArtifactRef, JobPosting, JobSummary, PlatformAdapter } from "./adapters/types";
import { BossAdapter } from "./adapters/boss";
import { LiepinAdapter } from "./adapters/liepin";
import { ZhilianAdapter } from "./adapters/zhilian";
import { LocalArtifactBridge } from "./transport/artifact-bridge";


const bridge = new LocalArtifactBridge();


function currentAdapter(): PlatformAdapter | undefined {
  const hostname = location.hostname;
  if (hostname.endsWith("zhipin.com")) return new BossAdapter(document, bridge);
  if (hostname.endsWith("liepin.com")) return new LiepinAdapter(document, bridge);
  if (hostname.endsWith("zhaopin.com")) return new ZhilianAdapter(document, bridge);
  return undefined;
}


async function collect(adapter: PlatformAdapter, limit: number) {
  const jobs: JobSummary[] = [];
  for await (const job of adapter.collectListings({ limit })) jobs.push(job);
  return jobs;
}


async function handle(message: Record<string, unknown>): Promise<unknown> {
  const adapter = currentAdapter();
  if (!adapter) return { status: "failed", reason: "unsupported_platform" };
  const payload = (message.payload ?? {}) as Record<string, unknown>;
  switch (message.type) {
    case "detectPage":
      return { page: adapter.detectPage() };
    case "collectListings":
      return collect(adapter, Math.min(100, Math.max(1, Number(payload.limit ?? 20))));
    case "extractJob":
      return adapter.extractJob(payload.job as JobSummary);
    case "preflight":
      return adapter.preflight(payload.job as JobPosting, payload.artifact as ArtifactRef);
    case "submit":
      return adapter.submit(
        payload.job as JobPosting,
        payload.artifact as ArtifactRef,
        String(payload.greeting ?? ""),
      );
    case "observeResult":
      return adapter.observeResult(String(payload.taskId ?? ""));
    case "stop":
      await adapter.stop();
      return { status: "stopped" };
    default:
      return { status: "failed", reason: "unknown_command" };
  }
}


chrome.runtime.onMessage.addListener((message: Record<string, unknown>, _sender, sendResponse) => {
  void handle(message).then(sendResponse, (error: unknown) =>
    sendResponse({ status: "failed", reason: String(error) }),
  );
  return true;
});


let lastPage = currentAdapter()?.detectPage();
const observer = new MutationObserver(() => {
  const page = currentAdapter()?.detectPage();
  if (page === "risk" && lastPage !== "risk") {
    void chrome.runtime.sendMessage({
      type: "riskDetected",
      payload: { url: location.href, detectedAt: new Date().toISOString() },
    });
  }
  lastPage = page;
});
observer.observe(document.documentElement, { childList: true, subtree: true });

