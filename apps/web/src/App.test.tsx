import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "./App";


const responses: Record<string, unknown> = {
  "/api/screening/presets": {
    precise: { name: "precise", minimum_score: 85, hr_active_within_days: 7, daily_limit: 10 },
    balanced: { name: "balanced", minimum_score: 70, hr_active_within_days: 30, daily_limit: 20 },
    broad: { name: "broad", minimum_score: 55, hr_active_within_days: null, daily_limit: 30 },
  },
  "/api/jobs": [
    {
      platform: "boss",
      platform_job_id: "boss-1",
      company: "示例科技",
      title: "Python 后端工程师",
      location: "深圳",
      salary_min_k: 20,
      salary_max_k: 30,
      snapshot_at: "2026-08-18T02:00:00Z",
    },
  ],
  "/api/tasks": [
    {
      id: "task-1",
      job_id: "boss-1",
      resume_version_id: "resume-1",
      greeting: "您好，期待沟通。",
      mode: "confirm_before_apply",
      platform: "boss",
      status: "requires_user_action",
      approved: true,
      last_error: null,
    },
    {
      id: "task-2",
      job_id: "boss-2",
      resume_version_id: "resume-2",
      greeting: "您好。",
      mode: "auto_apply",
      platform: "boss",
      status: "risk_stopped",
      approved: false,
      last_error: "captcha_detected",
    },
  ],
  "/api/settings/screening": {
    selected_preset: "precise",
    automation_mode: "confirm_before_apply",
    profile: {
      name: "precise",
      minimum_score: 85,
      daily_limit: 10,
      locations: [],
      salary_min_k: null,
      excluded_companies: [],
      required_keywords: [],
      excluded_keywords: [],
      experiences: [],
      educations: [],
      hr_active_within_days: 7,
      weights: { skills: 0.45, experience: 0.25, industry: 0.15, education: 0.05, preference: 0.1 },
    },
  },
  "/api/proposals": [
    {
      id: "pending-1",
      job_id: "boss-1",
      kind: "pending_claim",
      target_section: "项目经历",
      proposed_text: "将处理效率提升 30%",
      source_claim_ids: [],
      status: "pending",
      approved_job_id: null,
    },
  ],
};


beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = typeof input === "string" ? input : input.toString();
      return new Response(JSON.stringify(responses[path]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});


afterEach(() => vi.unstubAllGlobals());


it("defaults to precise screening and confirmation mode while exposing all modes", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "岗位编排台" })).toBeInTheDocument();
  const preset = screen.getByRole("combobox", { name: "筛选预设" });
  const mode = screen.getByRole("combobox", { name: "运行模式" });

  expect(preset).toHaveValue("precise");
  expect(mode).toHaveValue("confirm_before_apply");
  expect(screen.getByRole("option", { name: "人工确认后投递" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "高分岗位自动投递" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "仅生成待确认内容" })).toBeInTheDocument();

  const minimumScore = screen.getByRole("spinbutton", { name: "最低匹配分" });
  expect(minimumScore).toHaveValue(85);
  await userEvent.clear(minimumScore);
  await userEvent.type(minimumScore, "78");
  expect(preset).toHaveValue("custom");

  await userEvent.selectOptions(mode, "prepare_only");
  expect(mode).toHaveValue("prepare_only");
});


it("shows supported platforms and safety-critical queue states", async () => {
  render(<App />);

  await waitFor(() => expect(screen.getByText("示例科技")).toBeInTheDocument());
  expect(screen.getAllByText("Boss直聘").length).toBeGreaterThan(0);
  expect(screen.getByText("猎聘")).toBeInTheDocument();
  expect(screen.getByText("智联招聘")).toBeInTheDocument();
  expect(screen.getByText("等待人工完成附件")).toBeInTheDocument();
  expect(screen.getAllByText("风险停机").length).toBeGreaterThan(0);
  expect(screen.getByText("captcha_detected")).toBeInTheDocument();
  expect(screen.getByText("将处理效率提升 30%")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "仅当前岗位" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "加入长期事实库" })).toBeInTheDocument();
});
