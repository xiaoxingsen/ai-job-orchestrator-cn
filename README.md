# JobFlow CN

一个 Windows 优先、单用户、本地运行的 AI 求职编排系统：从国内招聘网站采集和筛选岗位，按每个 JD 生成事实可追溯的专属 DOCX/PDF 简历，再以用户选择的模式准备或提交首次沟通。

> 当前版本：`v0.1.0` 工程实现。Boss、猎聘和智联适配器已通过本地 HTML 契约测试；Boss 是首发目标。真实网站 DOM、账号风控和平台条款会变化，发布前仍必须用本人账号做有限人工冒烟。项目不会绕过验证码、风险页或登录限制。

## 已实现

- FastAPI + SQLite + Alembic 本地编排服务。
- React/Vite/TypeScript 工作台：岗位、筛选预设、三种运行模式、队列和安全状态。
- Chrome/Edge Manifest V3 插件：Boss、猎聘、智联统一适配器接口和版本化数据选择器。
- 三种可切换模式：
  - `confirm_before_apply`：人工确认后投递（首次启动默认）。
  - `auto_apply`：高分岗位自动投递，存在未审批建议时自动使用保守简历。
  - `prepare_only`：仅生成待确认内容，不提交。
- 精准 / 平衡 / 广覆盖预设，默认阈值分别为 85 / 70 / 55，每日上限 10 / 20 / 30。
- 事实库、`safe_rewrite` / `pending_claim` / `gap_warning`、当前岗位与长期事实库两级批准、拒绝负面记忆。
- 中文 DOCX/PDF 生成、ATS 文本回读测试、不可变文件名和 SHA-256 绑定。
- 持久任务和命令账本；`submitting` 中断后先观察平台结果，禁止直接重放。
- 一次性插件配对令牌、Origin 绑定、回环地址限制、路径穿越防护、JD 提示注入隔离。
- Windows DPAPI API Key 存储。
- 验证码、风险页、登录失效进入 `risk_stopped`；附件被平台阻止时进入 `requires_user_action`。
- Windows 托盘入口、数据库备份、PyInstaller 与 Inno Setup 配置。

## 架构

```text
React 工作台 ──HTTP──┐
                    │ 127.0.0.1:8765
MV3 插件 ─WebSocket─┤ FastAPI 编排服务 ─ SQLite / Alembic
  │                 │
  └─ 已登录招聘页面  └─ Apache-2.0 简历引擎 ─ DOCX / PDF / SHA-256
```

平台 Cookie 始终留在浏览器页面上下文；服务端和工作台没有接收 Cookie 的接口。插件只执行首次招呼语和简历提交，不持续代聊，也不自动交换微信或电话。

## 本地开发启动

要求：Windows 10/11、Python 3.11+（推荐 3.12）、Node.js 22+、Chrome 或 Edge。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

也可以手动运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m pip install -e ".\third_party\resume_engine"
npm install
npm run build
$env:JOBFLOW_WEB_ROOT = (Resolve-Path ".\apps\web\dist")
.\.venv\Scripts\python.exe -m job_orchestrator
```

工作台地址为 `http://127.0.0.1:8765`，API 文档为 `http://127.0.0.1:8765/api/docs`。

## 加载浏览器插件

1. 构建：`npm run build --workspace @job-orchestrator/extension`。
2. Chrome 打开 `chrome://extensions`，Edge 打开 `edge://extensions`。
3. 开启开发者模式，选择“加载已解压的扩展程序”。
4. 选择 `apps/extension/dist`。
5. 在工作台点击“生成插件配对令牌”，将令牌粘贴到插件弹窗。

插件只声明三个招聘站点和 `127.0.0.1:8765` 的 host permission。选择器包是 JSON 数据，不允许携带远程脚本或可执行字段。

## 测试与检查

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check apps\api\src apps\api\tests third_party\resume_engine\src
npm test
npm run typecheck
npm run build
```

测试覆盖领域筛选与状态机、事实审批、中文制品、数据库恢复、Alembic、配对与 DPAPI、三平台 DOM 契约、命令幂等、工作台模式与风险状态。

## 发布

```powershell
.\scripts\build-release.ps1 -Version 0.1.0
```

该脚本构建 Web 与插件、生成 PyInstaller one-folder 载荷和插件 ZIP。安装 Inno Setup 6 后，编译 `installer/windows/jobflow.iss` 可生成安装器。

发布前必须执行 `docs/release-checklist.md` 中的真实平台有限冒烟；CI 不访问招聘网站。

## 数据与安全

- 默认数据目录：`%LOCALAPPDATA%\JobFlowCN`。
- 正式简历生成后不原地覆盖，投递记录绑定版本、文件哈希和招呼语。
- 托盘菜单“备份数据库”会复制到 `Documents\JobFlowCN-Backups`。
- 不提供验证码绕过、风控规避、无限重试或后续 HR 自动回复。
- 使用前请确认招聘平台用户协议和当地法律允许相应自动化行为。

安全报告与威胁边界见 [SECURITY.md](SECURITY.md)。

## 许可证与来源

- 本仓库新代码：MIT，见 [LICENSE](LICENSE)。
- `third_party/resume_engine`：Apache-2.0，见其独立 [LICENSE](third_party/resume_engine/LICENSE)。
- 来源与未复制声明：见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

