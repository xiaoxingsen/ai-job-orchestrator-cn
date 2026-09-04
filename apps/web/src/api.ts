import type { ApplicationStatus, AutomationMode, Platform } from "@job-orchestrator/contracts";


export interface ScreeningPreset {
  name: string;
  minimum_score: number;
  hr_active_within_days: number | null;
  daily_limit: number;
  locations?: string[];
  salary_min_k?: number | null;
  excluded_companies?: string[];
  required_keywords?: string[];
  excluded_keywords?: string[];
  experiences?: string[];
  educations?: string[];
  weights?: MatchWeights;
}

export interface MatchWeights {
  skills: number;
  experience: number;
  industry: number;
  education: number;
  preference: number;
}

export interface ScreeningProfile extends ScreeningPreset {
  locations: string[];
  salary_min_k: number | null;
  excluded_companies: string[];
  required_keywords: string[];
  excluded_keywords: string[];
  experiences: string[];
  educations: string[];
  weights: MatchWeights;
}

export interface ScreeningSettings {
  selected_preset: "precise" | "balanced" | "broad" | "custom";
  automation_mode: AutomationMode;
  profile: ScreeningProfile;
}

export interface ApiJob {
  platform: Platform;
  platform_job_id: string;
  company: string;
  title: string;
  location: string;
  salary_min_k: number | null;
  salary_max_k: number | null;
  snapshot_at: string;
}

export interface ApiTask {
  id: string;
  job_id: string;
  resume_version_id: string;
  greeting: string;
  mode: AutomationMode;
  platform: Platform;
  status: ApplicationStatus;
  approved: boolean;
  last_error: string | null;
}

export interface ApiProposal {
  id: string;
  job_id: string;
  kind: "safe_rewrite" | "pending_claim" | "gap_warning";
  target_section: string;
  proposed_text: string;
  source_claim_ids: string[];
  status: "pending" | "approved_current_job" | "approved_fact_library" | "rejected";
  approved_job_id: string | null;
}


async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}


export function loadDashboard() {
  return Promise.all([
    getJson<Record<string, ScreeningPreset>>("/api/screening/presets"),
    getJson<ApiJob[]>("/api/jobs"),
    getJson<ApiTask[]>("/api/tasks"),
    getJson<ScreeningSettings>("/api/settings/screening"),
    getJson<ApiProposal[]>("/api/proposals"),
  ]).then(([presets, jobs, tasks, settings, proposals]) => ({
    presets,
    jobs,
    tasks,
    settings,
    proposals,
  }));
}

export async function saveScreeningSettings(settings: ScreeningSettings): Promise<ScreeningSettings> {
  const response = await fetch("/api/settings/screening", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) throw new Error(`保存筛选设置失败：HTTP ${response.status}`);
  return response.json() as Promise<ScreeningSettings>;
}

export async function issuePairingToken(): Promise<string> {
  const response = await fetch("/api/pairing/token", { method: "POST" });
  if (!response.ok) throw new Error("生成配对令牌失败");
  const payload = (await response.json()) as { token: string };
  return payload.token;
}

export async function decideProposal(
  proposalId: string,
  decision: "approve_current_job" | "approve_fact_library" | "reject",
): Promise<ApiProposal> {
  const response = await fetch(`/api/proposals/${encodeURIComponent(proposalId)}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!response.ok) throw new Error(`审批建议失败：HTTP ${response.status}`);
  return response.json() as Promise<ApiProposal>;
}
