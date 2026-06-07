# pocketStudio

pocketStudio 是一个受 TinyAGI 启发的 Python/FastAPI 多智能体编排后端。它把 agent、team、任务、队列、聊天室、调度、事件流和本地工作区管理放在同一个轻量系统里，适合在本机持续运行一组可协作的 AI agent。

项目同时包含一个已适配本地 API 的 TinyOffice 前端，以及一个 `pocketstudio` 命令行控制台。

## 核心能力

- Agent 管理：创建、更新、删除 agent，并为每个 agent 初始化独立 workspace。
- Skills 同步：根目录 `.agents/skills/` 会同步到 agent workspace，并映射给 `.codex/skills` 和 `.claude/skills`。
- Provider 适配：支持 `local`、OpenAI-compatible、Codex、Claude、OpenCode，以及自定义 provider。
- Team 协作：支持 chain 和 fanout。chain 模式会让 team leader 先规划、组员执行、leader 最后汇总组员结果。
- 队列系统：SQLite 持久化消息队列，支持 running/done/failed/dead 状态、重试、恢复 stale processing、响应队列。
- Chatroom：team 成员可以通过 `[#team: message]` 广播，也可以通过 chatroom API 交流。
- 项目和任务：内置 projects、tasks、comments、任务排序和 assignee 管理。
- 调度和 heartbeat：支持定时任务、手动 fire、agent heartbeat tick 和状态清理。
- 运行过程可视化：Codex provider 会把可展示的运行事件、工具调用和进度摘要映射到 SSE 和 visualizer。
- 终端 visualizer：可在 CMD/PowerShell 中原地刷新 team 运行状态和 chatroom。
- TinyOffice 前端：`tinyoffice/` 提供 Web UI，用于管理 agent、team、tasks、settings 和运行状态。

## 目录结构

```text
pocketStudio/              FastAPI 后端、服务层、provider、CLI
pocketStudio/api/          REST API 路由
pocketStudio/services/     agent/team/queue/task/schedule/worker 等业务服务
pocketStudio/providers/    local/openai/codex/claude/opencode provider 适配
pocketStudio/channels/     外部消息通道
tinyoffice/                Next.js 前端
tests/                     pytest 测试
docs/                      项目结构、函数索引和 TinyAGI 映射文档
tools/                     文档生成等维护脚本
.agents/skills/            根共享 skills
.pocketStudio/             默认运行时数据目录
```

## 环境要求

- Python 3.11+
- Node.js 20+，仅运行 TinyOffice 前端时需要
- Windows PowerShell 或 CMD 均可

推荐使用项目当前开发环境：

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe
```

也可以使用普通 venv：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

## 启动后端

开发模式：

```powershell
python -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777 --reload
```

使用项目常用 Python：

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

打开：

- API 文档：http://127.0.0.1:3777/docs
- 内置简易 UI：http://127.0.0.1:3777/
- API 前缀：http://127.0.0.1:3777/api

## 使用 CLI

安装为 editable 后会得到 `pocketstudio` 命令：

```powershell
python -m pip install -e ".[test]"
pocketstudio version
pocketstudio status
```

常用命令：

```powershell
pocketstudio daemon start
pocketstudio daemon status
pocketstudio daemon stop

pocketstudio agent list
pocketstudio agent add coder --name "Coder" --role "Python engineer" --provider local
pocketstudio team add dev --name "Dev Team" --agent coder --leader coder

pocketstudio send "@team:dev Plan a FastAPI service" --channel web --sender Web
pocketstudio queue status
pocketstudio worker tick
```

Provider 和进程：

```powershell
pocketstudio provider list
pocketstudio provider custom
pocketstudio process list
pocketstudio process kill coder
```

任务和项目：

```powershell
pocketstudio project list
pocketstudio project add Platform --description "Backend work" --prefix PLAT
pocketstudio task list
pocketstudio task add "Wire backend" --assignee coder --assignee-type agent
```

调度和 heartbeat：

```powershell
pocketstudio schedule list
pocketstudio schedule add --agent coder --message "Daily check" --cron "0 9 * * *"
pocketstudio heartbeat status
pocketstudio heartbeat tick --agent coder --force
```

## Visualizer

Team 运行看板：

```powershell
pocketstudio visualize
pocketstudio visualize --team dev
```

快照模式，适合调试或日志：

```powershell
pocketstudio visualize --once --no-clear
```

Chatroom 查看和发送：

```powershell
pocketstudio chatroom dev
pocketstudio chatroom dev --send "hello team"
```

Windows CMD 下 visualizer 会尽量启用 Virtual Terminal；如果不支持，会回退到 Windows Console API 原地清屏，不会持续往下追加刷新内容。

## TinyOffice 前端

先启动后端，然后在第二个终端运行：

```powershell
cd tinyoffice
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

打开：

```text
http://127.0.0.1:3000
```

构建检查：

```powershell
cd tinyoffice
npm run build
```

## REST API 快速示例

创建 agent：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/agents -ContentType application/json -Body '{"id":"coder","name":"Coder","role":"Python engineer","provider":"local"}'
```

创建 team：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/teams -ContentType application/json -Body '{"id":"dev","name":"Dev Team","mode":"chain","agent_ids":["coder"],"leaderAgent":"coder"}'
```

发送消息：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/messages -ContentType application/json -Body '{"target":"@team:dev","content":"Plan a FastAPI service","sender":"Web"}'
```

处理下一条队列：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/queue/process-next
```

查看事件：

```powershell
Invoke-RestMethod http://127.0.0.1:3777/api/events/office
```

SSE：

```text
http://127.0.0.1:3777/api/events/stream
```

## Team 协作模型

Team 支持两种模式：

- `chain`：leader 先执行，组员按顺序执行，最后 leader 汇总所有组员结果。
- `fanout`：所有成员并发执行，最终输出按 agent 分组拼接。

在 agent 输出中可以使用标签触发 team 通信：

```text
[@coder: implement the API]
[@coder,reviewer: inspect queue handling]
[#dev: post this to the team chatroom]
```

`[@agent: ...]` 会生成定向 teammate 消息。`[#team: ...]` 会写入 chatroom，并广播给 team 内其他成员。

## 运行时数据

默认运行目录：

```text
.pocketStudio/
```

常见内容：

```text
.pocketStudio/settings.json
.pocketStudio/pocketStudio.db
.pocketStudio/workspace/<agent_id>/
.pocketStudio/logs/pocketstudio.log
```

可用环境变量：

```powershell
$env:POCKETSTUDIO_POCKETSTUDIO_HOME="D:\path\to\runtime"
$env:POCKETSTUDIO_SQLITE_JOURNAL_MODE="WAL"
$env:POCKETSTUDIO_WORKER_ENABLED="true"
```

默认 SQLite journal mode 是 `MEMORY`，适合本地和 Windows 沙箱兼容。更接近生产的本机运行可以改为 `WAL`。

## 测试

运行全量测试：

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests -q -p no:cacheprovider
```

常用 focused tests：

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_orchestrator.py -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_visualizer.py tests\test_cli.py -q -p no:cacheprovider
```

修改 Python 函数或模块后，重新生成结构和函数文档：

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe tools\generate_project_docs.py
```

## 维护文档

- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.md`：中文项目结构和函数索引。
- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.en.md`：英文项目结构和函数索引。

