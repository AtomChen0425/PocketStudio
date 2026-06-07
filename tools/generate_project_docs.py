from __future__ import annotations

import ast
from pathlib import Path
from typing import Literal


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "pocketStudio"
DOCS = ROOT / "docs"


Lang = Literal["zh", "en"]


TEXT = {
    "zh": {
        "title": "pocketStudio 项目结构与函数用法",
        "intro": "本文档由 `tools/generate_project_docs.py` 根据 Python 后端源码生成，用来帮助维护者快速定位模块职责和函数入口。",
        "structure": "项目结构",
        "rules": "维护约定",
        "index": "函数索引",
        "function": "Function",
        "method": "Method",
        "usage": "用法",
        "class_desc": "类、数据模型、服务对象或异常类型。",
        "root_module": "包入口或应用入口。",
        "project_module": "项目模块。",
        "module_purposes": {
            "api": "FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。",
            "channels": "外部消息渠道适配层，例如 Telegram 的收发、配对和投递。",
            "core": "核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。",
            "providers": "Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。",
            "services": "业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。",
            "static": "FastAPI 内置的轻量备用前端资源。",
        },
        "structure_items": [
            "`pocketStudio/api/`: FastAPI 路由与 TinyAGI/TinyOffice 兼容响应。",
            "`pocketStudio/channels/`: 外部渠道桥接，当前包含 Telegram。",
            "`pocketStudio/core/`: 配置、数据库、依赖注入、ID、运行时和 JSON 文件工具。",
            "`pocketStudio/providers/`: 本地、OpenAI-compatible、Codex、Claude/OpenCode CLI 等 provider 适配。",
            "`pocketStudio/services/`: 业务服务层，承载主要领域逻辑。",
            "`pocketStudio/static/`: 内置备用 UI。",
            "`tests/`: pytest 行为测试与兼容契约测试。",
            "`docs/`: 架构、映射和维护文档。",
        ],
        "rules_items": [
            "路由层保持轻薄：复杂业务逻辑放到 `services/`。",
            "外部模型或命令执行放到 `providers/`，外部消息渠道放到 `channels/`。",
            "API 响应整形优先复用 `pocketStudio/api/payloads.py`。",
            "settings JSON 文件读写优先复用 `pocketStudio/core/json_store.py`。",
            "新增或移动函数后运行 `python tools/generate_project_docs.py` 更新本文档和英文版文档。",
        ],
        "descriptions": {
            "dunder": "Python 对象生命周期或协议方法。",
            "get": "读取单个资源、状态或派生视图。",
            "list": "列出资源集合或查询结果。",
            "create": "创建资源、安装内容或追加关系。",
            "update": "更新或持久化已有资源。",
            "delete": "删除资源或清理状态。",
            "validate": "校验输入或修复必需的运行状态。",
            "queue": "队列、响应或消息流转操作。",
            "control": "控制后台 worker、调度器或处理流程。",
            "run": "执行 provider、编排流程、事件或外部消息处理。",
            "convert": "转换、解析或格式化内部数据。",
            "payload": "构造 API/兼容层响应或请求载荷。",
            "method": "所属服务/类型的辅助方法。",
            "helper": "模块级辅助函数；修改前请先查看调用方和测试契约。",
        },
    },
    "en": {
        "title": "pocketStudio Project Structure and Function Usage",
        "intro": "This document is generated from the Python backend source by `tools/generate_project_docs.py` so maintainers can quickly locate module responsibilities and function entry points.",
        "structure": "Project Structure",
        "rules": "Maintenance Rules",
        "index": "Function Index",
        "function": "Function",
        "method": "Method",
        "usage": "Usage",
        "class_desc": "Class, data model, service object, or exception type.",
        "root_module": "Package entry point or application entry point.",
        "project_module": "Project module.",
        "module_purposes": {
            "api": "FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.",
            "channels": "External channel adapters, such as Telegram receive, pairing, and delivery logic.",
            "core": "Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.",
            "providers": "Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.",
            "services": "Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.",
            "static": "Small bundled fallback UI served by FastAPI.",
        },
        "structure_items": [
            "`pocketStudio/api/`: FastAPI routes and TinyAGI/TinyOffice compatibility responses.",
            "`pocketStudio/channels/`: External channel bridges; currently includes Telegram.",
            "`pocketStudio/core/`: Configuration, database, dependency injection, IDs, runtime, and JSON file helpers.",
            "`pocketStudio/providers/`: Local, OpenAI-compatible, Codex, Claude/OpenCode CLI, and other provider adapters.",
            "`pocketStudio/services/`: Business service layer that owns the main domain logic.",
            "`pocketStudio/static/`: Bundled fallback UI.",
            "`tests/`: pytest behavior tests and compatibility contract tests.",
            "`docs/`: Architecture, mapping, and maintenance documentation.",
        ],
        "rules_items": [
            "Keep route modules thin: put complex business logic in `services/`.",
            "Put external model or command execution in `providers/`; put external message channels in `channels/`.",
            "Reuse `pocketStudio/api/payloads.py` for API response shaping.",
            "Reuse `pocketStudio/core/json_store.py` for settings JSON file reads and writes.",
            "After adding or moving functions, run `python tools/generate_project_docs.py` to update both language versions.",
        ],
        "descriptions": {
            "dunder": "Python object lifecycle or protocol method.",
            "get": "Reads one resource, status object, or derived view.",
            "list": "Lists resources or query results.",
            "create": "Creates a resource, installs content, or adds a relationship.",
            "update": "Updates or persists an existing resource.",
            "delete": "Deletes a resource or clears state.",
            "validate": "Validates input or repairs required runtime state.",
            "queue": "Queue, response, or message flow operation.",
            "control": "Controls a background worker, scheduler, or processing flow.",
            "run": "Runs a provider, orchestration flow, event handler, or external message handler.",
            "convert": "Converts, parses, or formats internal data.",
            "payload": "Builds API or compatibility-layer response/request payloads.",
            "method": "Helper method for its service or type.",
            "helper": "Module-level helper. Review callers and tests before changing behavior.",
        },
    },
}


OUTPUTS = {
    "zh": DOCS / "PROJECT_STRUCTURE_AND_FUNCTIONS.md",
    "en": DOCS / "PROJECT_STRUCTURE_AND_FUNCTIONS.en.md",
}


def table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def code_cell(value: str) -> str:
    return f"`{table_cell(value)}`"


def module_summary(path: Path, lang: Lang) -> str:
    parts = path.relative_to(BACKEND).parts
    if len(parts) == 1:
        return TEXT[lang]["root_module"]
    return TEXT[lang]["module_purposes"].get(parts[0], TEXT[lang]["project_module"])


def description_key(name: str) -> str:
    public_name = name.lstrip("_")
    if name.startswith("__"):
        return "dunder"
    if public_name.startswith("get_") or public_name == "get":
        return "get"
    if public_name.startswith("list") or public_name == "list":
        return "list"
    if public_name.startswith(("create", "add", "install")) or public_name == "create":
        return "create"
    if public_name.startswith(("update", "save", "write", "set")) or public_name == "update":
        return "update"
    if public_name.startswith(("delete", "remove", "clear", "revoke")) or public_name == "delete":
        return "delete"
    if public_name.startswith(("validate", "ensure", "repair")):
        return "validate"
    if public_name.startswith(("enqueue", "queue", "retry", "ack", "prune", "recover")):
        return "queue"
    if public_name.startswith(("start", "stop", "restart", "pause", "resume", "tick", "fire", "process")):
        return "control"
    if public_name.startswith(("run", "dispatch", "broadcast", "emit", "handle")):
        return "run"
    if public_name.startswith(("to_", "from_", "parse", "decode", "extract", "strip", "convert", "format", "normalize")):
        return "convert"
    if public_name.endswith("_payload") or public_name.endswith("_config") or "payload" in public_name:
        return "payload"
    return "helper"


def describe_function(name: str, *, is_method: bool, lang: Lang) -> str:
    key = description_key(name)
    if key == "helper" and is_method:
        key = "method"
    return TEXT[lang]["descriptions"][key]


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return ast.unparse(node.args)
    except Exception:
        return ""


def function_rows(nodes: list[ast.AST], *, is_method: bool, lang: Lang) -> list[str]:
    rows = []
    for node in nodes:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = signature(node)
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        name = code_cell(f"{prefix}{node.name}({args})")
        usage = table_cell(describe_function(node.name, is_method=is_method, lang=lang))
        rows.append(f"| {name} | {usage} |")
    return rows


def module_section(path: Path, lang: Lang) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_name = path.relative_to(ROOT).as_posix()
    lines = [f"### `{module_name}`", "", module_summary(path, lang), ""]

    top_level = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if top_level:
        lines.extend([f"| {TEXT[lang]['function']} | {TEXT[lang]['usage']} |", "|---|---|"])
        lines.extend(function_rows(top_level, is_method=False, lang=lang))
        lines.append("")
    for cls in classes:
        bases = f"({', '.join(ast.unparse(base) for base in cls.bases)})" if cls.bases else ""
        lines.extend([f"#### `{table_cell(cls.name + bases)}`", "", TEXT[lang]["class_desc"], ""])
        methods = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if methods:
            lines.extend([f"| {TEXT[lang]['method']} | {TEXT[lang]['usage']} |", "|---|---|"])
            lines.extend(function_rows(methods, is_method=True, lang=lang))
            lines.append("")
    return lines


def build_document(lang: Lang) -> str:
    lines = [
        f"# {TEXT[lang]['title']}",
        "",
        TEXT[lang]["intro"],
        "",
        f"## {TEXT[lang]['structure']}",
        "",
    ]
    lines.extend(f"- {item}" for item in TEXT[lang]["structure_items"])
    lines.extend(["", f"## {TEXT[lang]['rules']}", ""])
    lines.extend(f"- {item}" for item in TEXT[lang]["rules_items"])
    lines.extend(["", f"## {TEXT[lang]['index']}", ""])
    for path in sorted(BACKEND.rglob("*.py")):
        lines.extend(module_section(path, lang))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for lang, path in OUTPUTS.items():
        path.write_text(build_document(lang), encoding="utf-8")


if __name__ == "__main__":
    main()
