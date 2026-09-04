import { Window } from "happy-dom";

import { IdempotentCommandExecutor } from "../src/commands/idempotent";
import { BossAdapter } from "../src/adapters/boss";
import { LiepinAdapter } from "../src/adapters/liepin";
import { ZhilianAdapter } from "../src/adapters/zhilian";
import type {
  ArtifactRef,
  AttachmentBridge,
  JobSummary,
  PlatformAdapter,
  SelectorBundle,
} from "../src/adapters/types";


const selectors: Omit<SelectorBundle, "platform"> = {
  schemaVersion: 1,
  selectorVersion: "2026.08.18-test",
  selectors: {
    listingCard: "[data-job-card]",
    listingLink: "[data-job-link]",
    title: "[data-title]",
    company: "[data-company]",
    description: "[data-description]",
    salary: "[data-salary]",
    location: "[data-location]",
    experience: "[data-experience]",
    education: "[data-education]",
    hrActivity: "[data-hr-active]",
    captcha: "[data-captcha]",
    riskPage: "[data-risk]",
    loginRequired: "[data-login]",
    greetingInput: "[data-greeting]",
    submitButton: "[data-submit]",
    attachmentInput: "[data-attachment]",
    successMarker: "[data-submitted]",
  },
};


class TestAttachmentBridge implements AttachmentBridge {
  calls = 0;

  constructor(private readonly result: boolean) {}

  async attach(_input: HTMLInputElement, _artifact: ArtifactRef): Promise<boolean> {
    this.calls += 1;
    return this.result;
  }
}


function page(platform: "boss" | "liepin" | "zhilian", extra = "") {
  const window = new Window({ url: `https://example.test/${platform}/job-42` });
  window.document.body.innerHTML = `
    <article data-job-card>
      <a data-job-link href="https://example.test/${platform}/job-42" data-job-id="job-42">
        <span data-title>Python 后端工程师</span>
      </a>
      <span data-company>示例科技</span>
      <span data-salary>20-30K·14薪</span>
      <span data-location>深圳</span>
      <span data-experience>3-5年</span>
      <span data-education>本科</span>
    </article>
    <section data-description>负责 FastAPI、SQLite 与自动化测试</section>
    <span data-hr-active>3日内活跃</span>
    ${extra}
  `;
  return window;
}


function adapterFor(platform: "boss" | "liepin" | "zhilian", bridge: AttachmentBridge) {
  const window = page(platform);
  const bundle: SelectorBundle = { ...selectors, platform };
  const constructors = { boss: BossAdapter, liepin: LiepinAdapter, zhilian: ZhilianAdapter };
  return new constructors[platform](window.document as unknown as Document, bridge, bundle);
}


async function listings(adapter: PlatformAdapter): Promise<JobSummary[]> {
  const result: JobSummary[] = [];
  for await (const item of adapter.collectListings({ limit: 20 })) result.push(item);
  return result;
}


describe.each(["boss", "liepin", "zhilian"] as const)("%s adapter contract", (platform) => {
  it("collects and normalizes a listing and full job", async () => {
    const adapter = adapterFor(platform, new TestAttachmentBridge(true));
    const summaries = await listings(adapter);
    const posting = await adapter.extractJob(summaries[0]!);

    expect(summaries).toHaveLength(1);
    expect(posting.platform).toBe(platform);
    expect(posting.platformJobId).toBe("job-42");
    expect(posting.title).toBe("Python 后端工程师");
    expect(posting.company).toBe("示例科技");
    expect(posting.salaryMinK).toBe(20);
    expect(posting.salaryMaxK).toBe(30);
    expect(posting.description).toContain("FastAPI");
  });

  it("stops on captcha instead of trying to bypass it", async () => {
    const window = page(platform, "<div data-captcha>请完成验证</div>");
    const bundle: SelectorBundle = { ...selectors, platform };
    const constructors = { boss: BossAdapter, liepin: LiepinAdapter, zhilian: ZhilianAdapter };
    const adapter = new constructors[platform](
      window.document as unknown as Document,
      new TestAttachmentBridge(true),
      bundle,
    );
    const posting = await adapter.extractJob({
      platform,
      platformJobId: "job-42",
      url: window.location.href,
      title: "Python 后端工程师",
      company: "示例科技",
    });

    const result = await adapter.preflight(posting, {
      name: "resume.pdf",
      path: "artifacts/resume.pdf",
      sha256: "a".repeat(64),
      downloadUrl: "http://127.0.0.1:8765/api/artifacts/resume.pdf",
      mimeType: "application/pdf",
    });

    expect(result.status).toBe("risk_stopped");
    expect(result.reasons).toContain("captcha_detected");
  });
});


it("requires user action when the platform blocks attachment automation", async () => {
  const adapter = adapterFor("boss", new TestAttachmentBridge(false));
  const [summary] = await listings(adapter);
  const posting = await adapter.extractJob(summary!);
  const artifact: ArtifactRef = {
    name: "resume.pdf",
    path: "artifacts/resume.pdf",
    sha256: "b".repeat(64),
    downloadUrl: "http://127.0.0.1:8765/api/artifacts/resume.pdf",
    mimeType: "application/pdf",
  };

  const result = await adapter.submit(posting, artifact, "您好，期待沟通。此消息仅发送一次");

  expect(result.status).toBe("requires_user_action");
  expect(result.artifactPath).toBe("artifacts/resume.pdf");
});


it("executes the same command id only once", async () => {
  const executor = new IdempotentCommandExecutor();
  let submits = 0;
  const command = async () => {
    submits += 1;
    return { status: "submitted" as const, remoteId: "chat-42" };
  };

  const first = await executor.execute("command-42", command);
  const second = await executor.execute("command-42", command);

  expect(first).toEqual(second);
  expect(submits).toBe(1);
});
