import { useEffect, useMemo, useState } from "react";
import type { AutomationMode, Platform } from "@job-orchestrator/contracts";

import {
  decideProposal,
  issuePairingToken,
  loadDashboard,
  saveScreeningSettings,
  type ApiJob,
  type ApiProposal,
  type ApiTask,
  type ScreeningProfile,
  type ScreeningPreset,
} from "./api";
import "./styles.css";


const modeLabels: Record<AutomationMode, string> = {
  confirm_before_apply: "人工确认后投递",
  auto_apply: "高分岗位自动投递",
  prepare_only: "仅生成待确认内容",
};

const platformLabels: Record<Platform, string> = {
  boss: "Boss直聘",
  liepin: "猎聘",
  zhilian: "智联招聘",
  mock: "本地仿真",
};

const statusLabels: Record<string, string> = {
  queued: "等待处理",
  preparing: "生成专属简历",
  ready_for_confirmation: "等待投递确认",
  prepared: "内容已准备",
  submitting: "正在投递",
  submitted: "已投递",
  requires_user_action: "等待人工完成附件",
  failed: "失败",
  risk_stopped: "风险停机",
};

const navItems = ["岗位编排台", "岗位库", "简历版本", "建议审批", "投递队列", "统计", "设置"];

const defaultProfile: ScreeningProfile = {
  name: "precise",
  minimum_score: 85,
  daily_limit: 10,
  hr_active_within_days: 7,
  locations: [],
  salary_min_k: null,
  excluded_companies: [],
  required_keywords: [],
  excluded_keywords: [],
  experiences: [],
  educations: [],
  weights: { skills: 0.45, experience: 0.25, industry: 0.15, education: 0.05, preference: 0.1 },
};


function salary(job: ApiJob): string {
  if (job.salary_min_k == null || job.salary_max_k == null) return "薪资面议";
  return `${job.salary_min_k}-${job.salary_max_k}K`;
}


function PlatformCards() {
  return (
    <section className="platform-grid" aria-label="招聘平台">
      {(["boss", "liepin", "zhilian"] as const).map((platform, index) => (
        <article className="platform-card" key={platform}>
          <span className={`platform-dot platform-dot--${platform}`} />
          <div>
            <strong>{platformLabels[platform]}</strong>
            <small>{index === 0 ? "首发适配 · 可执行" : "适配器已内置 · 需实站校验"}</small>
          </div>
          <span className="status-chip">本地浏览器</span>
        </article>
      ))}
    </section>
  );
}


function QueueTable({ tasks }: { tasks: ApiTask[] }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">APPLICATION QUEUE</span>
          <h2>投递队列</h2>
        </div>
        <span className="muted">重启后从 SQLite 恢复</span>
      </div>
      {tasks.length === 0 ? (
        <div className="empty">暂无投递任务。采集岗位后可生成专属简历。</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>任务</th><th>平台</th><th>模式</th><th>状态</th><th>说明</th></tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td><code>{task.job_id}</code></td>
                  <td>{platformLabels[task.platform]}</td>
                  <td>{modeLabels[task.mode]}</td>
                  <td>
                    <span className={`task-status task-status--${task.status}`}>
                      {statusLabels[task.status] ?? task.status}
                    </span>
                  </td>
                  <td className="muted">{task.last_error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}


function ProposalPanel({
  proposals,
  onDecision,
}: {
  proposals: ApiProposal[];
  onDecision: (id: string, decision: "approve_current_job" | "approve_fact_library" | "reject") => void;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div><span className="eyebrow">FACT APPROVAL</span><h2>建议审批</h2></div>
        <span className="muted">未审批内容不会进入正式简历</span>
      </div>
      {proposals.length === 0 ? <div className="empty">当前没有待确认的简历建议。</div> : (
        <div className="proposal-list">
          {proposals.map((proposal) => (
            <article key={proposal.id}>
              <div className="proposal-copy">
                <span>{proposal.target_section} · {proposal.job_id}</span>
                <strong>{proposal.proposed_text}</strong>
                <small>{proposal.kind === "pending_claim" ? "AI 新增事实 · 需要人工确认" : proposal.kind}</small>
              </div>
              {proposal.status === "pending" ? (
                <div className="proposal-actions">
                  <button type="button" onClick={() => onDecision(proposal.id, "approve_current_job")}>仅当前岗位</button>
                  <button type="button" onClick={() => onDecision(proposal.id, "approve_fact_library")}>加入长期事实库</button>
                  <button className="danger-button" type="button" onClick={() => onDecision(proposal.id, "reject")}>拒绝</button>
                </div>
              ) : <span className={`proposal-state proposal-state--${proposal.status}`}>{proposal.status}</span>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}


export function App() {
  const [activeNav, setActiveNav] = useState("岗位编排台");
  const [preset, setPreset] = useState("precise");
  const [mode, setMode] = useState<AutomationMode>("confirm_before_apply");
  const [presets, setPresets] = useState<Record<string, ScreeningPreset>>({});
  const [profile, setProfile] = useState<ScreeningProfile>(defaultProfile);
  const [jobs, setJobs] = useState<ApiJob[]>([]);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [proposals, setProposals] = useState<ApiProposal[]>([]);
  const [error, setError] = useState("");
  const [pairingToken, setPairingToken] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    let alive = true;
    void loadDashboard().then(
      (data) => {
        if (!alive) return;
        setPresets(data.presets);
        setJobs(data.jobs);
        setTasks(data.tasks);
        setPreset(data.settings.selected_preset);
        setMode(data.settings.automation_mode);
        setProfile(data.settings.profile);
        setProposals(data.proposals);
      },
      (reason: unknown) => alive && setError(String(reason)),
    );
    return () => {
      alive = false;
    };
  }, []);

  const metrics = useMemo(
    () => ({
      jobs: jobs.length,
      pending: tasks.filter((task) => task.status === "ready_for_confirmation").length,
      submitted: tasks.filter((task) => task.status === "submitted").length,
      stopped: tasks.filter((task) => task.status === "risk_stopped").length,
    }),
    [jobs, tasks],
  );

  async function createPairingToken() {
    try {
      setPairingToken(await issuePairingToken());
    } catch (reason) {
      setError(String(reason));
    }
  }

  function applyPreset(value: string) {
    setPreset(value);
    const selected = presets[value];
    if (!selected) return;
    setProfile({
      ...defaultProfile,
      ...selected,
      name: value,
      locations: selected.locations ?? [],
      excluded_companies: selected.excluded_companies ?? [],
      required_keywords: selected.required_keywords ?? [],
      excluded_keywords: selected.excluded_keywords ?? [],
      experiences: selected.experiences ?? [],
      educations: selected.educations ?? [],
      weights: selected.weights ?? defaultProfile.weights,
    });
  }

  function changeProfile<K extends keyof ScreeningProfile>(key: K, value: ScreeningProfile[K]) {
    setPreset("custom");
    setProfile((current) => ({ ...current, name: "custom", [key]: value }));
    setSaved("");
  }

  function commaList(value: string): string[] {
    return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
  }

  async function persistSettings() {
    try {
      await saveScreeningSettings({
        selected_preset: preset as "precise" | "balanced" | "broad" | "custom",
        automation_mode: mode,
        profile,
      });
      setSaved("设置已保存到本机");
    } catch (reason) {
      setError(String(reason));
    }
  }

  async function applyProposalDecision(
    proposalId: string,
    decision: "approve_current_job" | "approve_fact_library" | "reject",
  ) {
    try {
      const updated = await decideProposal(proposalId, decision);
      setProposals((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(String(reason));
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">J</span><span>JobFlow CN<small>本地 AI 求职编排</small></span></div>
        <nav aria-label="主导航">
          {navItems.map((item) => (
            <button
              className={activeNav === item ? "nav-item nav-item--active" : "nav-item"}
              key={item}
              onClick={() => setActiveNav(item)}
              type="button"
            >
              <span aria-hidden="true">{item.slice(0, 1)}</span>{item}
            </button>
          ))}
        </nav>
        <div className="privacy-note">
          <strong>隐私边界</strong>
          <span>数据保存在本机；招聘平台 Cookie 不离开浏览器。</span>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div><span className="eyebrow">LOCAL-FIRST WORKSPACE</span><h1>岗位编排台</h1><p>筛选岗位、审批事实、生成简历，再按所选模式投递。</p></div>
          <button className="secondary-button" type="button" onClick={() => void createPairingToken()}>
            生成插件配对令牌
          </button>
        </header>

        {pairingToken && <div className="pair-token"><span>一次性令牌</span><code>{pairingToken}</code></div>}
        {error && <div className="error-banner" role="alert">本地服务连接异常：{error}</div>}

        <section className="control-bar">
          <label>
            <span>筛选预设</span>
            <select aria-label="筛选预设" value={preset} onChange={(event) => applyPreset(event.target.value)}>
              <option value="precise">精准</option>
              <option value="balanced">平衡</option>
              <option value="broad">广覆盖</option>
              <option value="custom">自定义</option>
            </select>
          </label>
          <label>
            <span>运行模式</span>
            <select
              aria-label="运行模式"
              value={mode}
              onChange={(event) => setMode(event.target.value as AutomationMode)}
            >
              {Object.entries(modeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <div className="preset-summary">
            <span>匹配分 <strong>{profile.minimum_score}+</strong></span>
            <span>每日上限 <strong>{profile.daily_limit}</strong></span>
            <span>HR 活跃 <strong>{profile.hr_active_within_days ? `${profile.hr_active_within_days} 日` : "不限"}</strong></span>
          </div>
        </section>

        <details className="advanced-panel" open>
          <summary>高级筛选条件与权重</summary>
          <div className="advanced-grid">
            <label><span>最低匹配分</span><input aria-label="最低匹配分" type="number" min="0" max="100" value={profile.minimum_score} onChange={(event) => changeProfile("minimum_score", Number(event.target.value))} /></label>
            <label><span>每日投递上限</span><input type="number" min="1" max="100" value={profile.daily_limit} onChange={(event) => changeProfile("daily_limit", Number(event.target.value))} /></label>
            <label><span>HR 活跃天数</span><input type="number" min="0" max="365" value={profile.hr_active_within_days ?? ""} onChange={(event) => changeProfile("hr_active_within_days", event.target.value ? Number(event.target.value) : null)} /></label>
            <label><span>最低月薪（K）</span><input type="number" min="0" value={profile.salary_min_k ?? ""} onChange={(event) => changeProfile("salary_min_k", event.target.value ? Number(event.target.value) : null)} /></label>
            <label className="wide"><span>地点（逗号分隔）</span><input value={profile.locations.join("，")} onChange={(event) => changeProfile("locations", commaList(event.target.value))} /></label>
            <label className="wide"><span>必须关键词</span><input value={profile.required_keywords.join("，")} onChange={(event) => changeProfile("required_keywords", commaList(event.target.value))} /></label>
            <label className="wide"><span>排除关键词</span><input value={profile.excluded_keywords.join("，")} onChange={(event) => changeProfile("excluded_keywords", commaList(event.target.value))} /></label>
            <label className="wide"><span>排除公司</span><input value={profile.excluded_companies.join("，")} onChange={(event) => changeProfile("excluded_companies", commaList(event.target.value))} /></label>
            <label className="wide"><span>经验条件</span><input value={profile.experiences.join("，")} onChange={(event) => changeProfile("experiences", commaList(event.target.value))} /></label>
            <label className="wide"><span>学历条件</span><input value={profile.educations.join("，")} onChange={(event) => changeProfile("educations", commaList(event.target.value))} /></label>
          </div>
          <div className="weight-grid">
            {(Object.keys(profile.weights) as Array<keyof typeof profile.weights>).map((key) => (
              <label key={key}><span>{key}</span><input type="number" min="0" max="1" step="0.05" value={profile.weights[key]} onChange={(event) => changeProfile("weights", { ...profile.weights, [key]: Number(event.target.value) })} /></label>
            ))}
          </div>
          <div className="advanced-actions"><span>{saved || "权重总和必须等于 1"}</span><button type="button" onClick={() => void persistSettings()}>保存筛选设置</button></div>
        </details>

        <PlatformCards />

        <section className="metric-grid">
          <article><span>已采集岗位</span><strong>{metrics.jobs}</strong><small>已标准化去重</small></article>
          <article><span>等待确认</span><strong>{metrics.pending}</strong><small>不自动越过审批</small></article>
          <article><span>已投递</span><strong>{metrics.submitted}</strong><small>绑定简历哈希</small></article>
          <article><span>风险停机</span><strong>{metrics.stopped}</strong><small>验证码/登录失效</small></article>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><span className="eyebrow">JOB LIBRARY</span><h2>最近岗位</h2></div><span className="muted">硬过滤先于 AI 评分</span></div>
          {jobs.length === 0 ? <div className="empty">等待插件从招聘页面采集岗位。</div> : (
            <div className="table-wrap"><table><thead><tr><th>职位</th><th>公司</th><th>平台</th><th>地点</th><th>薪资</th></tr></thead>
              <tbody>{jobs.map((job) => <tr key={`${job.platform}:${job.platform_job_id}`}><td><strong>{job.title}</strong></td><td>{job.company}</td><td>{platformLabels[job.platform]}</td><td>{job.location}</td><td>{salary(job)}</td></tr>)}</tbody>
            </table></div>
          )}
        </section>

        <ProposalPanel proposals={proposals} onDecision={(id, decision) => void applyProposalDecision(id, decision)} />

        <QueueTable tasks={tasks} />
      </main>
    </div>
  );
}
