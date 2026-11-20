#!/usr/bin/env python3
"""Approval-gated local method library for cross-project AI experience transfer."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
DEFAULT_ROOT = Path("<your-experience-library>")
SECRET_RE = re.compile(
    r"(?i)(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization\s*:|bearer\s+[a-z0-9._-]+|password\s*[:=]|secret\s*[:=]|cookie\s*[:=]|openid\s*[:=])"
)
HEADING_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
EXTRACT_HEADINGS = ("经验", "历史坑", "复盘", "验证结果", "关键决定", "可复用", "教训")
APPROVAL_PLACEHOLDERS = {"需人工补充", "未明确", "待补充", "todo", "tbd"}


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def today() -> str:
    return dt.datetime.now().astimezone().date().isoformat()


def safe_text(value: str, field: str, allow_empty: bool = False) -> str:
    value = (value or "").strip()
    if not value and not allow_empty:
        raise ValueError(f"{field} 不能为空")
    if SECRET_RE.search(value):
        raise ValueError(f"{field} 疑似包含凭据或敏感认证信息，已拒绝写入")
    return value


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({part.strip() for part in value.split(",") if part.strip()})


def slug(text: str, fallback: str = "method") -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:36]
    return ascii_part or fallback


def make_id(prefix: str, seed: str) -> str:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
    unique = f"{time.time_ns()}|{uuid.uuid4().hex}"
    digest = hashlib.sha256(f"{seed}|{unique}".encode()).hexdigest()[:8]
    return f"{prefix}-{stamp}-{digest}"


def unique_id(prefix: str, seed: str, existing: Iterable[str]) -> str:
    occupied = set(existing)
    for _ in range(8):
        candidate = make_id(prefix, seed)
        if candidate not in occupied:
            return candidate
    raise RuntimeError("无法生成唯一 ID，已停止写入以避免覆盖")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def empty_state() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "policy": default_policy(), "candidates": {}, "methods": {}, "retrospectives": {}, "injections": {}}


def default_policy() -> dict[str, Any]:
    return {"approval_mode": "manual", "authorized_at": None, "authorized_by": None, "reason": None}


class Library:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.state_path = self.root / ".state.json"
        self.audit_path = self.root / "AUDIT.jsonl"
        self.lock_path = self.root / ".lock"

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("candidates", "methods", "history", "retrospectives", "injections", "validation"):
            (self.root / name).mkdir(exist_ok=True)
        if not self.state_path.exists():
            atomic_write(self.state_path, json.dumps(empty_state(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            self.audit("library_initialized", {"schema_version": SCHEMA_VERSION})
        self.render_index(self.load())

    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError("方法库尚未初始化，请先运行 init")
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("不支持的方法库 schema 版本")
        data.setdefault("policy", default_policy())
        return data

    def save(self, state: dict[str, Any]) -> None:
        atomic_write(self.state_path, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        self.render_index(state)

    def audit(self, event: str, detail: dict[str, Any]) -> None:
        append_line(self.audit_path, {"at": now_iso(), "event": event, "detail": detail})

    def render_index(self, state: dict[str, Any]) -> None:
        pending = [c for c in state["candidates"].values() if c["status"] == "pending"]
        approved = [m for m in state["methods"].values() if m["status"] == "approved"]
        open_injections = [i for i in state["injections"].values() if i.get("status") == "open"]
        lines = [
            "---",
            "type: experience-library-index",
            f"updated: {today()}",
            "permalink: main-knowledge/codex/experience-system/index",
            "---",
            "",
            "# AI 经验传承方法库",
            "",
            "> 只有符合当前入库策略并已成为正式方法的经验可用于任务前注入；pending 候选与复盘本身不参与检索。",
            "",
            "## 当前状态",
            "",
            f"- 待审批候选：{len(pending)}",
            f"- 已批准方法：{len(approved)}",
            f"- 复盘记录：{len(state['retrospectives'])}",
            f"- 注入记录：{len(state['injections'])}",
            f"- 未闭环任务：{len(open_injections)}",
            f"- 入库模式：{state.get('policy', default_policy())['approval_mode']}",
            "",
            "## 待审批候选",
            "",
        ]
        if pending:
            lines.extend([f"- [[candidates/{c['id']}|{c['title']}]]（来源：{c['source_project']}）" for c in sorted(pending, key=lambda x: x["created_at"], reverse=True)])
        else:
            lines.append("- 暂无")
        lines.extend(["", "## 已批准方法", ""])
        if approved:
            lines.extend([f"- [[methods/{m['id']}|{m['title']}]] · v{m['version']}" for m in sorted(approved, key=lambda x: x["title"])])
        else:
            lines.append("- 暂无")
        lines.extend(["", "## 权限边界", "", "- 来源项目只读。", "- `manual` 模式逐条审批；`bootstrap_auto` 只自动升级字段完整且符合持续授权的候选。", "- 检索只返回正式方法。", "- 方法变更保留旧版本和授权审计。", ""])
        atomic_write(self.root / "INDEX.md", "\n".join(lines))

    def add_candidate(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        candidate_id = unique_id("C", data["title"], state["candidates"])
        candidate = {
            "id": candidate_id,
            "status": "pending",
            "created_at": now_iso(),
            "source_project": safe_text(data["source_project"], "source_project"),
            "source_ref": safe_text(data.get("source_ref") or "未提供", "source_ref"),
            "title": safe_text(data["title"], "title"),
            "rule": safe_text(data["rule"], "rule"),
            "applies_to": safe_text(data["applies_to"], "applies_to"),
            "not_for": safe_text(data.get("not_for") or "未明确", "not_for"),
            "evidence": safe_text(data["evidence"], "evidence"),
            "risk": safe_text(data.get("risk") or "误用会造成范围外泛化", "risk"),
            "verification": safe_text(data.get("verification") or "在下一项目记录采用与未采用结果", "verification"),
            "tags": split_csv(data.get("tags")),
            "method_id": (data.get("method_id") or "").strip() or None,
        }
        if candidate["method_id"] and candidate["method_id"] not in state["methods"]:
            raise ValueError("method_id 不存在，不能作为修订候选")
        state["candidates"][candidate_id] = candidate
        atomic_write(self.root / "candidates" / f"{candidate_id}.md", render_candidate(candidate))
        self.audit("candidate_created", {"candidate_id": candidate_id, "source_project": candidate["source_project"]})
        return candidate


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_candidate(c: dict[str, Any]) -> str:
    if c["status"] == "approved":
        footer = f"> 已按方法库策略升级为正式方法：`{c.get('approved_method_id')}`。"
    elif c["status"] == "rejected":
        footer = "> 已拒绝；保留本记录仅用于审计，不参与任务前检索。"
    else:
        footer = "> 当前仅为待处理候选，不得作为长期方法注入。"
    return "\n".join([
        "---", f"id: {c['id']}", f"status: {c['status']}", f"created_at: {yaml_scalar(c['created_at'])}",
        f"source_project: {yaml_scalar(c['source_project'])}", f"source_ref: {yaml_scalar(c['source_ref'])}",
        f"method_id: {yaml_scalar(c.get('method_id'))}", f"tags: {yaml_scalar(c['tags'])}", "---", "",
        f"# 候选：{c['title']}", "", f"## 建议规则\n\n{c['rule']}", f"## 适用范围\n\n{c['applies_to']}",
        f"## 不适用\n\n{c['not_for']}", f"## 证据\n\n{c['evidence']}", f"## 风险\n\n{c['risk']}",
        f"## 跨项目验证\n\n{c['verification']}", "", footer, ""
    ])


def render_method(m: dict[str, Any]) -> str:
    history = m.get("decision_history", [])
    decisions = "\n".join(f"- {d['at']} · {d['approved_by']} · {d['note']}" for d in history) or "- 无"
    return "\n".join([
        "---", f"id: {m['id']}", f"status: {m['status']}", f"version: {yaml_scalar(m['version'])}",
        f"updated_at: {yaml_scalar(m['updated_at'])}", f"tags: {yaml_scalar(m['tags'])}", "---", "",
        f"# {m['title']}", "", f"## 方法\n\n{m['rule']}", f"## 适用范围\n\n{m['applies_to']}",
        f"## 不适用\n\n{m['not_for']}", f"## 证据\n\n{m['evidence']}", f"## 风险\n\n{m['risk']}",
        f"## 验证清单\n\n{m['verification']}", "## 审批记录", "", decisions, ""
    ])


def bump_patch(version: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def tokenize(text: str) -> set[str]:
    lowered = text.lower()
    words = set(re.findall(r"[a-z0-9][a-z0-9._-]*", lowered))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    for run in chinese_runs:
        words.add(run)
        words.update(run[i:i + 2] for i in range(max(0, len(run) - 1)))
    return {w for w in words if w}


def method_score(method: dict[str, Any], query: str) -> int:
    q = tokenize(query)
    if not q:
        return 0
    title_tags = tokenize(method["title"] + " " + " ".join(method["tags"]))
    body = tokenize(" ".join([method["rule"], method["applies_to"], method["verification"]]))
    return 5 * len(q & title_tags) + 2 * len(q & body)


def render_injection(record: dict[str, Any], methods: list[dict[str, Any]]) -> str:
    lines = [
        "---", f"id: {record['id']}", f"created_at: {yaml_scalar(record['created_at'])}",
        f"project: {yaml_scalar(record['project'])}", f"project_type: {yaml_scalar(record['project_type'])}",
        f"status: {record.get('status', 'legacy')}", f"retrospective_id: {yaml_scalar(record.get('retrospective_id'))}", "---", "",
        f"# 任务前经验注入：{record['task']}", "", f"检索词：{record['query']}", "",
        "> 这些方法是辅助约束，不能替代当前项目的产品地图、源码证据或实际验证。", ""
    ]
    if record.get("status") == "open":
        lines.extend(["> 本任务尚未闭环：结束前必须使用本注入 ID 写入任务后复盘。", ""])
    elif record.get("status") == "closed":
        lines.extend([f"> 已由复盘 `{record.get('retrospective_id')}` 闭环。", ""])
    if not methods:
        lines.extend(["## 未命中", "", "没有足够相关的已批准方法。不要为了凑数注入候选或低相关经验。", ""])
    for idx, method in enumerate(methods, 1):
        lines.extend([
            f"## {idx}. {method['title']} · v{method['version']}", "", f"- 方法 ID：`{method['id']}`",
            f"- 适用：{method['applies_to']}", f"- 不适用：{method['not_for']}", f"- 风险：{method['risk']}", "",
            method["rule"], "", "验证：", "", method["verification"], ""
        ])
    return "\n".join(lines)


def cmd_init(lib: Library, _args: argparse.Namespace) -> int:
    lib.initialize()
    print(f"initialized: {lib.root}")
    return 0


def cmd_status(lib: Library, _args: argparse.Namespace) -> int:
    state = lib.load()
    counts = {
        "pending_candidates": sum(c.get("status") == "pending" for c in state["candidates"].values()),
        "malformed_candidates": sum(c.get("status") not in {"pending", "approved", "rejected"} for c in state["candidates"].values()),
        "approved_methods": sum(m["status"] == "approved" for m in state["methods"].values()),
        "retrospectives": len(state["retrospectives"]), "injections": len(state["injections"]),
        "open_injections": sum(i.get("status") == "open" for i in state["injections"].values()),
        "approval_mode": state.get("policy", default_policy())["approval_mode"],
    }
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


def candidate_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {key: getattr(args, key, None) for key in ("source_project", "source_ref", "title", "rule", "applies_to", "not_for", "evidence", "risk", "verification", "tags", "method_id")}


def cmd_candidate_add(lib: Library, args: argparse.Namespace) -> int:
    with lib.locked():
        state = lib.load()
        candidate = lib.add_candidate(state, candidate_payload(args))
        lib.save(state)
    print(json.dumps({"candidate_id": candidate["id"], "status": candidate["status"]}, ensure_ascii=False))
    return 0


def cmd_candidate_list(lib: Library, args: argparse.Namespace) -> int:
    state = lib.load()
    items = [c for c in state["candidates"].values() if args.status == "all" or c["status"] == args.status]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_update(lib: Library, args: argparse.Namespace) -> int:
    editable = ("title", "rule", "applies_to", "not_for", "evidence", "risk", "verification")
    with lib.locked():
        state = lib.load()
        candidate = state["candidates"].get(args.candidate_id)
        if not candidate or candidate["status"] != "pending":
            raise ValueError("只有存在的 pending 候选可以补充")
        changed: list[str] = []
        for field in editable:
            value = getattr(args, field, None)
            if value is not None:
                candidate[field] = safe_text(value, field)
                changed.append(field)
        if args.tags is not None:
            candidate["tags"] = split_csv(args.tags)
            changed.append("tags")
        if not changed:
            raise ValueError("没有提供任何要更新的字段")
        candidate["updated_at"] = now_iso()
        atomic_write(lib.root / "candidates" / f"{candidate['id']}.md", render_candidate(candidate))
        lib.audit("candidate_updated", {"candidate_id": candidate["id"], "fields": changed})
        lib.save(state)
    print(json.dumps({"candidate_id": candidate["id"], "status": "pending", "updated_fields": changed}, ensure_ascii=False))
    return 0


def cmd_extract(lib: Library, args: argparse.Namespace) -> int:
    source = Path(args.source_file).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError("extract 只接受一个存在的 Markdown/TXT 文件，不扫描目录")
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    active = False
    found: list[str] = []
    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            active = any(key in heading.group(1) for key in EXTRACT_HEADINGS)
            continue
        bullet = BULLET_RE.match(line)
        if active and bullet:
            text = bullet.group(1).strip()
            if len(text) >= args.min_length and not SECRET_RE.search(text):
                found.append(text)
        if len(found) >= args.limit:
            break
    created: list[str] = []
    with lib.locked():
        state = lib.load()
        for item in found:
            title = item[:48] + ("…" if len(item) > 48 else "")
            candidate = lib.add_candidate(state, {
                "source_project": args.source_project, "source_ref": args.source_ref or source.name,
                "title": title, "rule": item, "applies_to": args.applies_to,
                "not_for": "需人工补充", "evidence": f"来自 {args.source_ref or source.name} 的明确记录；尚需人工核实可迁移性",
                "risk": "自动抽取可能丢失上下文或把项目特例误当通用规则",
                "verification": "人工补充边界后，在第二个项目记录是否命中、是否采用及结果",
                "tags": args.tags, "method_id": None,
            })
            created.append(candidate["id"])
        lib.save(state)
    print(json.dumps({"extracted": len(created), "candidate_ids": created, "skipped_or_unmatched": max(0, len(lines) - len(found))}, ensure_ascii=False))
    return 0


def approval_incomplete(candidate: dict[str, Any]) -> list[str]:
    return [field for field in ("rule", "applies_to", "not_for", "evidence", "risk", "verification")
            if str(candidate.get(field) or "").strip().lower() in APPROVAL_PLACEHOLDERS]


def require_approval_authority(state: dict[str, Any], confirm: str) -> str:
    if confirm == "USER_APPROVED":
        return "per_item"
    if confirm == "BOOTSTRAP_AUTHORIZED" and state.get("policy", default_policy())["approval_mode"] == "bootstrap_auto":
        return "bootstrap_auto"
    raise ValueError("审批被拒绝：需要单条 USER_APPROVED，或已启用 bootstrap_auto 后使用 BOOTSTRAP_AUTHORIZED")


def promote_candidate(lib: Library, state: dict[str, Any], candidate: dict[str, Any], approved_by: str, note: str, authority: str) -> dict[str, Any]:
    incomplete = approval_incomplete(candidate)
    if incomplete:
        raise ValueError(f"候选边界未补齐，不能批准: {', '.join(incomplete)}；请先运行 candidate update")
    decision = {"at": now_iso(), "approved_by": safe_text(approved_by, "approved_by"), "note": safe_text(note, "decision_note"), "authority": authority}
    method_id = candidate.get("method_id")
    if method_id:
        previous = state["methods"][method_id]
        history_path = lib.root / "history" / method_id / f"v{previous['version']}.md"
        atomic_write(history_path, render_method(previous))
        version = bump_patch(previous["version"])
        decision_history = previous.get("decision_history", []) + [decision]
    else:
        method_id = f"M-{slug(candidate['title'])}-{hashlib.sha256(candidate['title'].encode()).hexdigest()[:6]}"
        if method_id in state["methods"]:
            method_id = unique_id("M", candidate["title"], state["methods"])
        version = "1.0.0"
        decision_history = [decision]
    method = {
        "id": method_id, "status": "approved", "version": version, "updated_at": now_iso(),
        "title": candidate["title"], "rule": candidate["rule"], "applies_to": candidate["applies_to"],
        "not_for": candidate["not_for"], "evidence": candidate["evidence"], "risk": candidate["risk"],
        "verification": candidate["verification"], "tags": candidate["tags"],
        "source_candidates": (state["methods"].get(method_id, {}).get("source_candidates", []) + [candidate["id"]]),
        "decision_history": decision_history,
    }
    state["methods"][method_id] = method
    candidate["status"] = "approved"
    candidate["decision"] = decision
    candidate["approved_method_id"] = method_id
    atomic_write(lib.root / "candidates" / f"{candidate['id']}.md", render_candidate(candidate))
    atomic_write(lib.root / "methods" / f"{method_id}.md", render_method(method))
    lib.audit("candidate_approved", {"candidate_id": candidate["id"], "method_id": method_id, "version": version, "approved_by": decision["approved_by"], "authority": authority})
    return {"candidate_id": candidate["id"], "method_id": method_id, "version": version, "status": "approved"}


def cmd_approve(lib: Library, args: argparse.Namespace) -> int:
    with lib.locked():
        state = lib.load()
        authority = require_approval_authority(state, args.confirm)
        candidate = state["candidates"].get(args.candidate_id)
        if not candidate or candidate["status"] != "pending":
            raise ValueError("候选不存在或已处理")
        result = promote_candidate(lib, state, candidate, args.approved_by, args.decision_note, authority)
        lib.save(state)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_approve_all(lib: Library, args: argparse.Namespace) -> int:
    with lib.locked():
        state = lib.load()
        authority = require_approval_authority(state, args.confirm)
        approved: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        pending = sorted((c for c in state["candidates"].values() if c["status"] == "pending"), key=lambda c: c["created_at"])
        for candidate in pending:
            incomplete = approval_incomplete(candidate)
            if incomplete:
                skipped.append({"candidate_id": candidate["id"], "reason": f"incomplete: {','.join(incomplete)}"})
                continue
            approved.append(promote_candidate(lib, state, candidate, args.approved_by, args.decision_note, authority))
        lib.audit("bulk_approval_completed", {"authority": authority, "approved": [x["candidate_id"] for x in approved], "skipped": skipped})
        lib.save(state)
    print(json.dumps({"approved": approved, "skipped": skipped}, ensure_ascii=False, indent=2))
    return 0


def cmd_policy_set(lib: Library, args: argparse.Namespace) -> int:
    if args.confirm != "USER_AUTHORIZED":
        raise ValueError("策略变更被拒绝：需要 --confirm USER_AUTHORIZED")
    with lib.locked():
        state = lib.load()
        policy = {"approval_mode": args.approval_mode, "authorized_at": now_iso(), "authorized_by": safe_text(args.authorized_by, "authorized_by"), "reason": safe_text(args.reason, "reason")}
        state["policy"] = policy
        lib.audit("approval_policy_changed", policy)
        lib.save(state)
    print(json.dumps(policy, ensure_ascii=False, indent=2))
    return 0


def cmd_policy_show(lib: Library, _args: argparse.Namespace) -> int:
    print(json.dumps(lib.load().get("policy", default_policy()), ensure_ascii=False, indent=2))
    return 0


def cmd_reject(lib: Library, args: argparse.Namespace) -> int:
    if args.confirm != "USER_REJECTED":
        raise ValueError("拒绝决定未确认：需要 --confirm USER_REJECTED")
    with lib.locked():
        state = lib.load()
        candidate = state["candidates"].get(args.candidate_id)
        if not candidate or candidate["status"] != "pending":
            raise ValueError("候选不存在或已处理")
        candidate["status"] = "rejected"
        candidate["decision"] = {"at": now_iso(), "decided_by": safe_text(args.decided_by, "decided_by"), "note": safe_text(args.decision_note, "decision_note")}
        atomic_write(lib.root / "candidates" / f"{candidate['id']}.md", render_candidate(candidate))
        lib.audit("candidate_rejected", {"candidate_id": candidate["id"], "decided_by": candidate["decision"]["decided_by"]})
        lib.save(state)
    print(json.dumps({"candidate_id": candidate["id"], "status": "rejected"}, ensure_ascii=False))
    return 0


def find_methods(state: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    scored = [(method_score(m, query), m) for m in state["methods"].values() if m["status"] == "approved"]
    scored = [(score, method) for score, method in scored if score >= 4]
    scored.sort(key=lambda item: (-item[0], item[1]["title"]))
    return [dict(method, _score=score) for score, method in scored[:limit]]


def cmd_search(lib: Library, args: argparse.Namespace) -> int:
    state = lib.load()
    query = " ".join(filter(None, [args.query, args.project_type, args.task]))
    print(json.dumps(find_methods(state, query, args.limit), ensure_ascii=False, indent=2))
    return 0


def cmd_inject(lib: Library, args: argparse.Namespace) -> int:
    project = safe_text(args.project, "project")
    project_type = safe_text(args.project_type, "project_type")
    task = safe_text(args.task, "task")
    query_text = safe_text(args.query, "query")
    with lib.locked():
        state = lib.load()
        existing_open = [i for i in state["injections"].values() if i.get("status") == "open" and i["project"] == project and i["task"] == task]
        if existing_open:
            raise ValueError(f"该项目和任务已有未闭环注入: {existing_open[0]['id']}；请复用该 ID 写复盘，避免重复开工记录")
        combined = " ".join([query_text, project_type, task])
        methods = find_methods(state, combined, args.limit)
        record_id = unique_id("I", combined, state["injections"])
        record = {"id": record_id, "created_at": now_iso(), "project": project, "project_type": project_type, "task": task, "query": query_text, "method_ids": [m["id"] for m in methods], "status": "open", "retrospective_id": None, "closed_at": None}
        state["injections"][record_id] = record
        content = render_injection(record, methods)
        output = Path(args.output).expanduser().resolve() if args.output else lib.root / "injections" / f"{record_id}.md"
        if output != lib.root and lib.root not in output.parents:
            raise ValueError("注入包只能写入方法库目录，来源项目保持只读")
        atomic_write(output, content)
        lib.audit("methods_injected", {"injection_id": record_id, "project": project, "method_ids": record["method_ids"]})
        lib.save(state)
    print(content)
    print(f"\nINJECTION_ID: {record_id}\nSAVED: {output}", file=sys.stderr)
    return 0


def cmd_retro(lib: Library, args: argparse.Namespace) -> int:
    project = safe_text(args.project, "project")
    task = safe_text(args.task, "task")
    outcome = safe_text(args.outcome, "outcome")
    observations = safe_text(args.observations or "未补充", "observations")
    with lib.locked():
        state = lib.load()
        injection = state["injections"].get(args.injection_id)
        if not injection:
            raise ValueError("injection_id 不存在；任务复盘必须关联一次任务前注入")
        if injection.get("status") != "open":
            raise ValueError("injection_id 不是未闭环状态，不能重复关闭")
        if injection["project"] != project:
            raise ValueError("复盘项目必须与任务前注入的项目一致")
        unknown = [m for m in args.used_method if m not in state["methods"]]
        if unknown:
            raise ValueError(f"used_method 不存在: {', '.join(unknown)}")
        retro_id = unique_id("R", project + task, state["retrospectives"])
        record = {"id": retro_id, "created_at": now_iso(), "project": project, "task": task, "result": args.result, "outcome": outcome, "observations": observations, "used_methods": args.used_method, "injection_id": injection["id"], "candidate_ids": [], "promoted_method_ids": []}
        for lesson in args.lesson:
            lesson = safe_text(lesson, "lesson")
            candidate = lib.add_candidate(state, {
                "source_project": project, "source_ref": f"retrospectives/{retro_id}", "title": lesson[:48], "rule": lesson,
                "applies_to": args.lesson_applies_to or "需人工补充", "not_for": args.lesson_not_for or "需人工补充",
                "evidence": f"任务“{task}”的复盘结果：{outcome}", "risk": args.lesson_risk or "需人工补充",
                "verification": args.lesson_verification or "需人工补充", "tags": args.tags, "method_id": None,
            })
            record["candidate_ids"].append(candidate["id"])
            if state.get("policy", default_policy()).get("approval_mode") == "bootstrap_auto" and not approval_incomplete(candidate):
                promoted = promote_candidate(
                    lib, state, candidate,
                    state["policy"].get("authorized_by") or "user-authorized bootstrap",
                    "任务复盘产生完整候选，按初期持续授权自动入库",
                    "bootstrap_auto",
                )
                record["promoted_method_ids"].append(promoted["method_id"])
        state["retrospectives"][retro_id] = record
        injection["status"] = "closed"
        injection["closed_at"] = now_iso()
        injection["retrospective_id"] = retro_id
        methods_for_injection = [state["methods"][mid] for mid in injection["method_ids"] if mid in state["methods"]]
        atomic_write(lib.root / "injections" / f"{injection['id']}.md", render_injection(injection, methods_for_injection))
        method_lines = "\n".join(f"- `{m}`" for m in record["used_methods"]) or "- 未使用已批准方法"
        candidate_lines = "\n".join(f"- `[[../candidates/{c}|{c}]]`" for c in record["candidate_ids"]) or "- 无"
        if record["promoted_method_ids"]:
            promotion_lines = "\n".join(f"- `{m}`" for m in record["promoted_method_ids"])
        elif record["candidate_ids"]:
            promotion_lines = "- 无；候选保留 pending"
        else:
            promotion_lines = "- 本次复盘未生成新候选"
        content = "\n".join([
            "---", f"id: {retro_id}", f"created_at: {yaml_scalar(record['created_at'])}", f"project: {yaml_scalar(project)}", f"injection_id: {injection['id']}", f"result: {args.result}", "---", "",
            f"# 任务后复盘：{task}", "", f"## 实际结果\n\n{outcome}", f"## 观察与偏差\n\n{observations}",
            "## 本次采用的方法", "", method_lines, "", "## 新候选", "", candidate_lines, "",
            "## 自动入库结果", "", promotion_lines, "",
            "> `bootstrap_auto` 仅自动升级字段完整的候选；来源项目保持只读，其他外部权限不变。", ""
        ])
        path = lib.root / "retrospectives" / f"{retro_id}.md"
        atomic_write(path, content)
        lib.audit("retrospective_recorded", {"retrospective_id": retro_id, "injection_id": injection["id"], "project": project, "result": args.result, "candidate_ids": record["candidate_ids"]})
        lib.save(state)
    print(json.dumps({"retrospective_id": retro_id, "candidate_ids": record["candidate_ids"], "promoted_method_ids": record["promoted_method_ids"]}, ensure_ascii=False))
    return 0


def cmd_closure_check(lib: Library, args: argparse.Namespace) -> int:
    state = lib.load()
    open_items = [i for i in state["injections"].values() if i.get("status") == "open" and (not args.project or i["project"] == args.project)]
    open_items.sort(key=lambda item: item["created_at"])
    result = {"ok": not open_items, "project": args.project or None, "open_injections": open_items}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not open_items else 1


def cmd_verify(lib: Library, _args: argparse.Namespace) -> int:
    state = lib.load()
    errors: list[str] = []
    if state.get("policy", default_policy()).get("approval_mode") not in {"manual", "bootstrap_auto"}:
        errors.append("invalid approval policy mode")
    for cid, candidate in state["candidates"].items():
        if not (lib.root / "candidates" / f"{cid}.md").is_file():
            errors.append(f"missing candidate note: {cid}")
        if candidate.get("status") not in {"pending", "approved", "rejected"}:
            errors.append(f"candidate missing or invalid status: {cid}")
            continue
        missing = [f for f in ("source_project", "title", "rule", "applies_to", "not_for", "evidence", "risk", "verification") if f not in candidate]
        if missing:
            errors.append(f"candidate missing fields {','.join(missing)}: {cid}")
        if candidate["status"] == "approved" and candidate.get("approved_method_id") not in state["methods"]:
            errors.append(f"approved candidate missing method: {cid}")
    for mid, method in state["methods"].items():
        if method["status"] != "approved":
            errors.append(f"method not approved: {mid}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", method["version"]):
            errors.append(f"invalid version: {mid}")
        if not (lib.root / "methods" / f"{mid}.md").is_file():
            errors.append(f"missing method note: {mid}")
    for iid, injection in state["injections"].items():
        status = injection.get("status", "legacy")
        if status not in {"legacy", "open", "closed"}:
            errors.append(f"invalid injection status: {iid}")
        if status == "closed":
            retro_id = injection.get("retrospective_id")
            if retro_id not in state["retrospectives"]:
                errors.append(f"closed injection missing retrospective: {iid}")
            elif state["retrospectives"][retro_id].get("injection_id") != iid:
                errors.append(f"injection/retrospective mismatch: {iid}")
        if not (lib.root / "injections" / f"{iid}.md").is_file():
            errors.append(f"missing injection note: {iid}")
    audit_events = 0
    created_ids: dict[str, set[str]] = {"candidate_created": set(), "methods_injected": set(), "retrospective_recorded": set()}
    if lib.audit_path.exists():
        for line_no, line in enumerate(lib.audit_path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
                audit_events += 1
                kind = event.get("event")
                key_by_kind = {"candidate_created": "candidate_id", "methods_injected": "injection_id", "retrospective_recorded": "retrospective_id"}
                if kind in key_by_kind:
                    entity_id = event.get("detail", {}).get(key_by_kind[kind])
                    if entity_id in created_ids[kind]:
                        errors.append(f"duplicate audit entity id: {kind}/{entity_id}")
                    elif entity_id:
                        created_ids[kind].add(entity_id)
            except json.JSONDecodeError:
                errors.append(f"invalid audit json at line {line_no}")
    for mid, method in state["methods"].items():
        try:
            major, minor, patch = (int(x) for x in method["version"].split("."))
        except (ValueError, AttributeError):
            continue
        if major == 1 and minor == 0:
            for previous_patch in range(patch):
                expected = lib.root / "history" / mid / f"v1.0.{previous_patch}.md"
                if not expected.is_file():
                    errors.append(f"missing method history: {mid}/v1.0.{previous_patch}")
    result = {"ok": not errors, "errors": errors, "counts": {"candidates": len(state["candidates"]), "methods": len(state["methods"]), "retrospectives": len(state["retrospectives"]), "injections": len(state["injections"]), "open_injections": sum(i.get("status") == "open" for i in state["injections"].values()), "audit_events": audit_events}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("status").set_defaults(func=cmd_status)

    candidate = sub.add_parser("candidate")
    candidate_sub = candidate.add_subparsers(dest="candidate_command", required=True)
    add = candidate_sub.add_parser("add")
    for name in ("source-project", "title", "rule", "applies-to", "evidence"):
        add.add_argument(f"--{name}", required=True)
    for name in ("source-ref", "not-for", "risk", "verification", "tags", "method-id"):
        add.add_argument(f"--{name}")
    add.set_defaults(func=cmd_candidate_add)
    listing = candidate_sub.add_parser("list")
    listing.add_argument("--status", choices=("pending", "approved", "rejected", "all"), default="pending")
    listing.set_defaults(func=cmd_candidate_list)
    update = candidate_sub.add_parser("update")
    update.add_argument("candidate_id")
    for name in ("title", "rule", "applies-to", "not-for", "evidence", "risk", "verification", "tags"):
        update.add_argument(f"--{name}")
    update.set_defaults(func=cmd_candidate_update)

    extract = sub.add_parser("extract")
    extract.add_argument("--source-file", required=True)
    extract.add_argument("--source-project", required=True)
    extract.add_argument("--source-ref")
    extract.add_argument("--applies-to", default="相同技术栈、阶段和约束的项目")
    extract.add_argument("--tags")
    extract.add_argument("--limit", type=int, default=12)
    extract.add_argument("--min-length", type=int, default=12)
    extract.set_defaults(func=cmd_extract)

    approve = sub.add_parser("approve")
    approve.add_argument("candidate_id")
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--decision-note", required=True)
    approve.add_argument("--confirm", required=True)
    approve.set_defaults(func=cmd_approve)
    approve_all = sub.add_parser("approve-all")
    approve_all.add_argument("--approved-by", required=True)
    approve_all.add_argument("--decision-note", required=True)
    approve_all.add_argument("--confirm", required=True)
    approve_all.set_defaults(func=cmd_approve_all)
    reject = sub.add_parser("reject")
    reject.add_argument("candidate_id")
    reject.add_argument("--decided-by", required=True)
    reject.add_argument("--decision-note", required=True)
    reject.add_argument("--confirm", required=True)
    reject.set_defaults(func=cmd_reject)

    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("show").set_defaults(func=cmd_policy_show)
    policy_set = policy_sub.add_parser("set")
    policy_set.add_argument("--approval-mode", choices=("manual", "bootstrap_auto"), required=True)
    policy_set.add_argument("--authorized-by", required=True)
    policy_set.add_argument("--reason", required=True)
    policy_set.add_argument("--confirm", required=True)
    policy_set.set_defaults(func=cmd_policy_set)

    for name, func in (("search", cmd_search), ("inject", cmd_inject)):
        p = sub.add_parser(name)
        p.add_argument("--query", required=True)
        p.add_argument("--project", default="")
        p.add_argument("--project-type", default="")
        p.add_argument("--task", default="")
        p.add_argument("--limit", type=int, default=5)
        if name == "inject":
            p.add_argument("--output")
            p.get_default("func")
        p.set_defaults(func=func)

    retro = sub.add_parser("retro")
    retro.add_argument("--project", required=True)
    retro.add_argument("--task", required=True)
    retro.add_argument("--result", choices=("success", "partial", "failure"), required=True)
    retro.add_argument("--outcome", required=True)
    retro.add_argument("--observations")
    retro.add_argument("--injection-id", required=True)
    retro.add_argument("--used-method", action="append", default=[])
    retro.add_argument("--lesson", action="append", default=[])
    retro.add_argument("--lesson-applies-to")
    retro.add_argument("--lesson-not-for")
    retro.add_argument("--lesson-risk")
    retro.add_argument("--lesson-verification")
    retro.add_argument("--tags")
    retro.set_defaults(func=cmd_retro)
    closure = sub.add_parser("closure")
    closure.add_argument("--project")
    closure.set_defaults(func=cmd_closure_check)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    lib = Library(args.root)
    try:
        return args.func(lib, args)
    except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

