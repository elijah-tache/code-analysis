#!/usr/bin/env python3
"""devstate.py — deterministic state helper for the autonomous-dev skill.

Reads the project's planning documents (tasks.json, OPEN_QUESTIONS.md), the
persistent progress file (progress.json) and git, then reconciles them.
Standard library only. It never imports or executes project code.

Run from anywhere inside the repository:
    python3 .claude/skills/autonomous-dev/scripts/devstate.py <command> [...]

Commands (``--help`` on each for details):
    status [--json]                 Reconcile and report; read-only.
    init                            Create progress.json if it does not exist.
    sync                            Reconcile and write derived fields to progress.json.
    start TASK                      Make TASK the current task (in_progress).
    stage TASK STAGE                Record the current pipeline stage of TASK.
    record TASK --kind K --verdict V --summary S [--evidence E ...]
                                    Append an agent/orchestrator result to history.
    complete TASK                   Mark TASK done (requires tester PASS and reviewer
                                    APPROVE after the last developer run).
    committed TASK [--commit HASH]  Attach the commit (found via 'Task: TASK' trailer).
    block TASK --reason R [--questions Q01,Q02]
    fail TASK --reason R
    reopen TASK --reason R          Back to pending (e.g. unverified 'done').
    checkpoint --note N
    issue TEXT                      Add an outstanding issue.
    approval request TEXT | approval resolve N --granted|--denied [--note N]
    config [KEY VALUE]              Show or set a config value (JSON-parsed).

Exit codes: 0 ok, 1 usage/validation error, 2 guard refused the transition.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any

PROGRESS_SCHEMA_VERSION = 1
RESOLVED_QUESTION = re.compile(r"^\s*(resolved|answered|closed|accepted|withdrawn)\b", re.I)
TASK_ID = re.compile(r"\bT\d{3,}\b")
QUESTION_ID = re.compile(r"\bQ\d{2,}\b")
STAGES = ("selected", "implementing", "testing", "reviewing", "fixing", "committing")
TERMINAL = ("done",)
DEFAULT_CONFIG: dict[str, Any] = {
    "base_branch": "main",
    "work_branch": None,
    "max_attempts": 3,
    "allow_push": False,
    "allow_pr": False,
    "allow_network": False,
    "baseline_commit_approved": None,
}


# ---------------------------------------------------------------- utilities
def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def git(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)
    except FileNotFoundError:
        return 127, ""
    return p.returncode, p.stdout.strip()


def repo_root() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except FileNotFoundError:
        pass
    return os.getcwd()


ROOT = repo_root()


def path(name: str) -> str:
    return os.path.join(ROOT, name)


def atomic_write_json(file: str, data: Any) -> None:
    """Write JSON via temp file + fsync + os.replace so readers never see a partial file."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    d = os.path.dirname(file) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, file)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def die(msg: str, code: int = 1) -> None:
    print(f"devstate: {msg}", file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ loading
def load_tasks() -> dict[str, Any]:
    f = path("tasks.json")
    if not os.path.exists(f):
        die("tasks.json not found at repository root")
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("tasks"), list):
        die("tasks.json has no 'tasks' list")
    return data


def save_tasks(data: dict[str, Any]) -> None:
    atomic_write_json(path("tasks.json"), data)


def load_questions() -> dict[str, dict[str, Any]]:
    """Parse the markdown table in OPEN_QUESTIONS.md -> {QID: {status, resolved, blocks}}."""
    f = path("OPEN_QUESTIONS.md")
    out: dict[str, dict[str, Any]] = {}
    if not os.path.exists(f):
        return out
    cols: dict[str, int] | None = None
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            if not line.lstrip().startswith("|"):
                cols = None if not line.strip() else cols
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            lowered = [c.lower() for c in cells]
            if "id" in lowered and any(c.startswith("status") for c in lowered):
                cols = {
                    "id": lowered.index("id"),
                    "status": next(i for i, c in enumerate(lowered) if c.startswith("status")),
                    "blocks": next((i for i, c in enumerate(lowered) if c.startswith("block")), -1),
                    "question": next((i for i, c in enumerate(lowered) if c.startswith("question")), -1),
                }
                continue
            if cols is None or set(line.strip()) <= set("|-: "):
                continue
            qid = cells[cols["id"]] if cols["id"] < len(cells) else ""
            if not QUESTION_ID.fullmatch(qid):
                continue
            status = cells[cols["status"]] if cols["status"] < len(cells) else ""
            blocks = cells[cols["blocks"]] if 0 <= cols["blocks"] < len(cells) else ""
            question = cells[cols["question"]] if 0 <= cols["question"] < len(cells) else ""
            out[qid] = {
                "status": status,
                "resolved": bool(RESOLVED_QUESTION.match(status)),
                "blocks": sorted(set(TASK_ID.findall(blocks))),
                "question": question,
            }
    return out


def new_progress(tasks: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "project": tasks.get("project"),
        "created_at": now(),
        "updated_at": now(),
        "config": dict(DEFAULT_CONFIG),
        "current_task": None,
        "tasks": {t["id"]: empty_task_entry() for t in tasks["tasks"]},
        "completed": [],
        "blocked": [],
        "ready": [],
        "outstanding": [],
        "open_issues": [],
        "pending_approvals": [],
        "warnings": [],
        "last_checkpoint": None,
        "last_reconciled_at": None,
    }


def empty_task_entry() -> dict[str, Any]:
    return {
        "status": "pending",
        "attempts": 0,
        "stage": None,
        "blocked_reason": None,
        "blocking_questions": [],
        "commits": [],
        "evidence": [],
        "history": [],
        "completed_at": None,
    }


def load_progress(required: bool = True) -> dict[str, Any] | None:
    f = path("progress.json")
    if not os.path.exists(f):
        if required:
            die("progress.json not found; run 'init' first")
        return None
    with open(f, encoding="utf-8") as fh:
        p = json.load(fh)
    p.setdefault("config", {})
    for k, v in DEFAULT_CONFIG.items():
        p["config"].setdefault(k, v)
    for key in ("tasks",):
        p.setdefault(key, {})
    for key in ("completed", "blocked", "ready", "outstanding", "open_issues", "pending_approvals", "warnings"):
        p.setdefault(key, [])
    return p


def save_progress(p: dict[str, Any]) -> None:
    p["updated_at"] = now()
    atomic_write_json(path("progress.json"), p)


def entry(p: dict[str, Any], tid: str) -> dict[str, Any]:
    e = p["tasks"].setdefault(tid, empty_task_entry())
    for k, v in empty_task_entry().items():
        e.setdefault(k, v)
    return e


# ------------------------------------------------------------ reconciliation
def verdict_ok(e: dict[str, Any]) -> tuple[bool, str]:
    """True when the latest developer run is followed by tester PASS and reviewer APPROVE."""
    hist = e.get("history", [])
    last_dev = max((i for i, h in enumerate(hist) if h.get("kind") == "developer"), default=-1)
    if last_dev < 0:
        return False, "no developer result recorded"
    after = hist[last_dev + 1 :]
    tester = [h for h in after if h.get("kind") == "tester"]
    reviewer = [h for h in after if h.get("kind") == "reviewer"]
    if not tester or tester[-1].get("verdict") != "PASS":
        return False, "no tester PASS after the latest developer run"
    if not reviewer or reviewer[-1].get("verdict") != "APPROVE":
        return False, "no reviewer APPROVE after the latest developer run"
    return True, "verified"


def commits_for(tid: str, recorded: list[str]) -> tuple[list[str], list[str]]:
    """Return (commits reachable from HEAD that belong to tid, recorded hashes not reachable)."""
    found: list[str] = []
    code, out = git("log", "--format=%H", f"--grep=^Task: {tid}$", "--extended-regexp")
    if code == 0 and out:
        found = out.splitlines()
    missing: list[str] = []
    for h in recorded:
        c1, _ = git("cat-file", "-e", f"{h}^{{commit}}")
        c2, _ = git("merge-base", "--is-ancestor", h, "HEAD") if c1 == 0 else (1, "")
        if c1 != 0 or c2 != 0:
            missing.append(h)
        elif not any(f.startswith(h) or h.startswith(f) for f in found):
            found.append(h)
    return found, missing


def topo_order(tasks: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Stable Kahn topological order (ties broken by file order). Returns (order, cyclic ids)."""
    ids = [t["id"] for t in tasks]
    pos = {tid: i for i, tid in enumerate(ids)}
    deps = {t["id"]: [d for d in t.get("depends_on", []) if d in pos] for t in tasks}
    indeg = {tid: len(deps[tid]) for tid in ids}
    children: dict[str, list[str]] = {tid: [] for tid in ids}
    for tid, ds in deps.items():
        for d in ds:
            children[d].append(tid)
    ready = sorted([tid for tid in ids if indeg[tid] == 0], key=pos.get)
    order: list[str] = []
    while ready:
        tid = ready.pop(0)
        order.append(tid)
        for c in children[tid]:
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(c)
                ready.sort(key=pos.get)
    cyclic = [tid for tid in ids if tid not in order]
    return order, cyclic


def reconcile(tasks_doc: dict[str, Any], p: dict[str, Any] | None) -> dict[str, Any]:
    tasks = tasks_doc["tasks"]
    by_id = {t["id"]: t for t in tasks}
    questions = load_questions()
    warnings: list[str] = []
    order, cyclic = topo_order(tasks)
    if cyclic:
        warnings.append(f"dependency cycle among: {', '.join(cyclic)}")
    for t in tasks:
        for d in t.get("depends_on", []):
            if d not in by_id:
                warnings.append(f"{t['id']} depends on unknown task {d}")

    code, head = git("rev-parse", "HEAD")
    has_head = code == 0
    _, branch = git("rev-parse", "--abbrev-ref", "HEAD") if has_head else git("symbolic-ref", "--short", "HEAD")
    _, porcelain = git("status", "--porcelain", "--untracked-files=all")
    dirty = [line for line in porcelain.splitlines() if line.strip()]

    info: dict[str, dict[str, Any]] = {}
    for tid in order + cyclic:
        t = by_id[tid]
        e = (p or {}).get("tasks", {}).get(tid, empty_task_entry())
        doc_status = t.get("status", "pending")
        prog_status = e.get("status", "pending")
        status = prog_status if p else doc_status
        if p and doc_status != prog_status and not (doc_status == "pending" and prog_status == "blocked"):
            warnings.append(f"{tid}: tasks.json status '{doc_status}' != progress.json '{prog_status}'")

        verified = False
        found, missing = ([], [])
        if status == "done" or doc_status == "done":
            ok, why = verdict_ok(e) if p else (False, "no progress.json history")
            found, missing = commits_for(tid, e.get("commits", []))
            if missing:
                warnings.append(f"{tid}: recorded commit(s) not in HEAD history: {', '.join(missing)}")
            if not ok:
                warnings.append(f"{tid}: marked done but unverified ({why}); re-verify before relying on it")
            elif not found:
                warnings.append(f"{tid}: marked done but no commit with trailer 'Task: {tid}' reachable from HEAD")
            verified = ok and bool(found)

        qblock = sorted(
            {
                q
                for q, qi in questions.items()
                if not qi["resolved"] and (tid in qi["blocks"] or q in t.get("open_questions", []))
            }
            | {
                q
                for q in t.get("blocked_by", [])
                if QUESTION_ID.fullmatch(q) and not questions.get(q, {}).get("resolved", False)
            }
        )
        other_block = [b for b in t.get("blocked_by", []) if not QUESTION_ID.fullmatch(b)]
        info[tid] = {
            "id": tid,
            "title": t.get("title", ""),
            "phase": t.get("phase"),
            "status": status,
            "verified_done": verified,
            "commits": found,
            "question_blockers": qblock,
            "other_blockers": other_block,
            "manual_block": e.get("blocked_reason") if prog_status == "blocked" and not qblock else None,
            "attempts": e.get("attempts", 0),
            "depends_on": t.get("depends_on", []),
        }

    # Transitive root-cause blockers: unresolved questions on the task or any ancestor.
    root: dict[str, set[str]] = {}
    for tid in order:
        s = set(info[tid]["question_blockers"])
        for d in info[tid]["depends_on"]:
            if d in root and not info[d]["verified_done"]:
                s |= root[d]
        root[tid] = s
    for tid in cyclic:
        root[tid] = set(info[tid]["question_blockers"])

    ready: list[str] = []
    blocked: list[dict[str, Any]] = []
    for tid in order:
        i = info[tid]
        if i["verified_done"]:
            continue
        unmet = [d for d in i["depends_on"] if not (d in info and info[d]["verified_done"])]
        i["unmet_dependencies"] = unmet
        i["root_question_blockers"] = sorted(root[tid])
        reasons = []
        if i["question_blockers"]:
            reasons.append("unresolved question(s) " + ", ".join(i["question_blockers"]))
        if i["other_blockers"]:
            reasons.append("blocked_by " + ", ".join(i["other_blockers"]))
        if i["manual_block"]:
            reasons.append(str(i["manual_block"]))
        if i["status"] == "failed":
            reasons.append("failed after max attempts; needs user")
        if reasons:
            blocked.append({"task": tid, "reasons": reasons, "questions": i["question_blockers"]})
        elif not unmet and i["status"] in ("pending", "in_progress", "blocked", "done"):
            ready.append(tid)

    question_impact = {
        q: sorted(tid for tid in root if q in root[tid] and not info[tid]["verified_done"])
        for q, qi in questions.items()
        if not qi["resolved"]
    }
    current = (p or {}).get("current_task")
    complete_reasons = []
    if any(not i["verified_done"] for i in info.values()):
        complete_reasons.append(f"{sum(not i['verified_done'] for i in info.values())} task(s) not verified done")
    if question_impact:
        complete_reasons.append(f"{len(question_impact)} unresolved question(s)")
    if p and p.get("pending_approvals"):
        open_appr = [a for a in p["pending_approvals"] if a.get("state") == "requested"]
        if open_appr:
            complete_reasons.append(f"{len(open_appr)} pending approval(s)")
    if dirty:
        complete_reasons.append("working tree not clean")

    return {
        "repo_root": ROOT,
        "git": {"has_commits": has_head, "head": head if has_head else None, "branch": branch, "dirty": dirty},
        "progress_exists": p is not None,
        "current_task": current,
        "order": order,
        "tasks": info,
        "ready": ready,
        "next_task": (current or {}).get("id") if current else (ready[0] if ready else None),
        "blocked": blocked,
        "questions": questions,
        "question_impact": question_impact,
        "warnings": warnings,
        "project_complete": not complete_reasons,
        "incomplete_reasons": complete_reasons,
    }


# ------------------------------------------------------------------ commands
def cmd_status(a: argparse.Namespace) -> None:
    r = reconcile(load_tasks(), load_progress(required=False))
    if a.json:
        print(json.dumps(r, indent=2))
        return
    g = r["git"]
    print(f"repo: {r['repo_root']}")
    print(f"git: branch={g['branch']} head={(g['head'] or 'NO COMMITS')[:12]} dirty_files={len(g['dirty'])}")
    print(f"progress.json: {'present' if r['progress_exists'] else 'MISSING (run init)'}")
    done = [t for t in r["tasks"].values() if t["verified_done"]]
    print(f"tasks: {len(done)}/{len(r['tasks'])} verified done")
    if r["current_task"]:
        c = r["current_task"]
        print(f"current task: {c.get('id')} stage={c.get('stage')} since={c.get('started_at')}")
    print(f"ready: {', '.join(r['ready']) or '(none)'}")
    print(f"next: {r['next_task'] or '(none)'}")
    if r["blocked"]:
        print("directly blocked:")
        for b in r["blocked"]:
            print(f"  {b['task']}: {'; '.join(b['reasons'])}")
    if r["question_impact"]:
        print("unresolved questions -> tasks blocked (directly or via dependencies):")
        for q, ts in sorted(r["question_impact"].items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"  {q} [{r['questions'][q]['status']}] blocks {len(ts)}: {', '.join(ts)}")
    waiting = [t for t in r["tasks"].values() if not t["verified_done"] and t.get("unmet_dependencies") and t["id"] not in {b["task"] for b in r["blocked"]}]
    if waiting:
        print(f"waiting on dependencies: {', '.join(t['id'] for t in waiting)}")
    for w in r["warnings"]:
        print(f"WARNING: {w}")
    print(f"project complete: {'YES' if r['project_complete'] else 'no — ' + '; '.join(r['incomplete_reasons'])}")


def cmd_init(a: argparse.Namespace) -> None:
    if load_progress(required=False) is not None:
        print("progress.json already exists; leaving it unchanged")
        return
    tasks = load_tasks()
    p = new_progress(tasks)
    for t in tasks["tasks"]:
        if t.get("status") == "done":
            # Never trust pre-existing 'done' without our own verification history.
            p["tasks"][t["id"]]["status"] = "done"
    save_progress(p)
    _sync(p, tasks)
    print("created progress.json")


def _sync(p: dict[str, Any], tasks: dict[str, Any]) -> dict[str, Any]:
    for t in tasks["tasks"]:
        entry(p, t["id"])
    r = reconcile(tasks, p)
    for tid, i in r["tasks"].items():
        e = entry(p, tid)
        if e["status"] in ("pending", "blocked") and i["question_blockers"]:
            e["status"] = "blocked"
            e["blocking_questions"] = i["question_blockers"]
            e["blocked_reason"] = "unresolved question(s) " + ", ".join(i["question_blockers"])
        elif e["status"] == "blocked" and e.get("blocking_questions") and not i["question_blockers"]:
            # Questions were resolved: automatically reconsider the task.
            e["status"], e["blocking_questions"], e["blocked_reason"] = "pending", [], None
    _mirror_tasks(p, tasks)  # mirror first so the final reconcile sees consistent files
    r = reconcile(tasks, p)
    p["completed"] = [tid for tid in r["order"] if r["tasks"][tid]["verified_done"]]
    p["ready"] = r["ready"]
    p["blocked"] = r["blocked"]
    p["outstanding"] = [tid for tid in r["order"] if not r["tasks"][tid]["verified_done"]]
    p["question_impact"] = r["question_impact"]
    p["warnings"] = r["warnings"]
    p["last_reconciled_at"] = now()
    p["git"] = {"branch": r["git"]["branch"], "head": r["git"]["head"]}
    save_progress(p)
    return r


def _mirror_tasks(p: dict[str, Any], tasks: dict[str, Any]) -> None:
    """Mirror status/blocked_by into tasks.json (pending<->blocked only from questions)."""
    changed = False
    for t in tasks["tasks"]:
        e = p["tasks"].get(t["id"])
        if not e:
            continue
        if e["status"] != t.get("status"):
            t["status"] = e["status"]
            changed = True
        qb = e.get("blocking_questions", []) if e["status"] == "blocked" else []
        keep = [b for b in t.get("blocked_by", []) if not QUESTION_ID.fullmatch(b)]
        new = keep + [q for q in qb if q not in keep]
        if new != t.get("blocked_by", []):
            t["blocked_by"] = new
            changed = True
    if changed:
        save_tasks(tasks)


def cmd_sync(a: argparse.Namespace) -> None:
    tasks = load_tasks()
    r = _sync(load_progress(), tasks)
    print(f"synced: ready={','.join(r['ready']) or '-'} blocked={len(r['blocked'])} warnings={len(r['warnings'])}")


def _require_task(tasks: dict[str, Any], tid: str) -> None:
    if tid not in {t["id"] for t in tasks["tasks"]}:
        die(f"unknown task {tid}")


def cmd_start(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    cur = p.get("current_task")
    if cur and cur.get("id") != a.task:
        die(f"another task is current ({cur.get('id')}); finish, block or fail it first", 2)
    r = reconcile(tasks, p)
    if a.task not in r["ready"] and not (cur and cur.get("id") == a.task):
        die(f"{a.task} is not ready (see 'status')", 2)
    e = entry(p, a.task)
    e["status"], e["stage"] = "in_progress", "selected"
    p["current_task"] = {"id": a.task, "stage": "selected", "attempt": e["attempts"] + 1, "started_at": now()}
    save_progress(p)
    _mirror_tasks(p, tasks)
    print(f"started {a.task}")


def cmd_stage(a: argparse.Namespace) -> None:
    p = load_progress()
    cur = p.get("current_task") or {}
    if cur.get("id") != a.task:
        die(f"{a.task} is not the current task", 2)
    cur["stage"] = a.stage
    entry(p, a.task)["stage"] = a.stage
    save_progress(p)
    print(f"{a.task} stage={a.stage}")


def cmd_record(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    rec = {"at": now(), "kind": a.kind, "verdict": a.verdict, "summary": a.summary, "evidence": a.evidence or []}
    e["history"].append(rec)
    if a.kind == "developer":
        e["attempts"] += 1
        if p.get("current_task", {}) and p["current_task"].get("id") == a.task:
            p["current_task"]["attempt"] = e["attempts"]
    if a.evidence:
        e["evidence"].extend(a.evidence)
    save_progress(p)
    print(f"recorded {a.kind} {a.verdict} for {a.task} (attempt {e['attempts']})")


def cmd_complete(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    ok, why = verdict_ok(e)
    if not ok:
        die(f"refusing to complete {a.task}: {why}", 2)
    e["status"], e["stage"], e["completed_at"] = "done", "committing", now()
    for t in tasks["tasks"]:
        if t["id"] == a.task:
            t["status"] = "done"
            t["blocked_by"] = [b for b in t.get("blocked_by", []) if not QUESTION_ID.fullmatch(b)]
            ev = [x for x in e["evidence"] if x not in t.get("evidence", [])]
            t.setdefault("evidence", []).extend(ev)
    save_progress(p)
    save_tasks(tasks)
    print(f"{a.task} marked done; now commit with trailer 'Task: {a.task}' and run 'committed {a.task}'")


def cmd_committed(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    found, missing = commits_for(a.task, [a.commit] if a.commit else [])
    if missing or not found:
        die(f"no commit for {a.task} reachable from HEAD (expected trailer 'Task: {a.task}')", 2)
    for h in found:
        if h not in e["commits"]:
            e["commits"].append(h)
    e["stage"] = None
    if (p.get("current_task") or {}).get("id") == a.task:
        p["current_task"] = None
    p["last_checkpoint"] = {"at": now(), "task": a.task, "commit": found[0], "note": "task committed"}
    _sync(p, tasks)
    print(f"{a.task} committed as {found[0][:12]}")


def cmd_block(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    e["status"], e["blocked_reason"] = "blocked", a.reason
    e["blocking_questions"] = [q.strip() for q in (a.questions or "").split(",") if q.strip()]
    if (p.get("current_task") or {}).get("id") == a.task:
        p["current_task"] = None
    e["history"].append({"at": now(), "kind": "orchestrator", "verdict": "BLOCKED", "summary": a.reason, "evidence": []})
    _sync(p, tasks)
    print(f"{a.task} blocked: {a.reason}")


def cmd_fail(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    e["status"], e["blocked_reason"] = "failed", a.reason
    if (p.get("current_task") or {}).get("id") == a.task:
        p["current_task"] = None
    e["history"].append({"at": now(), "kind": "orchestrator", "verdict": "FAILED", "summary": a.reason, "evidence": []})
    _sync(p, tasks)
    print(f"{a.task} failed: {a.reason}")


def cmd_reopen(a: argparse.Namespace) -> None:
    tasks, p = load_tasks(), load_progress()
    _require_task(tasks, a.task)
    e = entry(p, a.task)
    e["status"], e["blocked_reason"], e["blocking_questions"], e["completed_at"] = "pending", None, [], None
    e["history"].append({"at": now(), "kind": "orchestrator", "verdict": "REOPENED", "summary": a.reason, "evidence": []})
    _sync(p, tasks)
    print(f"{a.task} reopened: {a.reason}")


def cmd_checkpoint(a: argparse.Namespace) -> None:
    p = load_progress()
    _, head = git("rev-parse", "HEAD")
    p["last_checkpoint"] = {"at": now(), "task": (p.get("current_task") or {}).get("id"), "commit": head or None, "note": a.note}
    save_progress(p)
    print("checkpoint saved")


def cmd_issue(a: argparse.Namespace) -> None:
    p = load_progress()
    p["open_issues"].append({"at": now(), "text": a.text, "task": a.task})
    save_progress(p)
    print(f"issue #{len(p['open_issues']) - 1} recorded")


def cmd_approval(a: argparse.Namespace) -> None:
    p = load_progress()
    if a.action == "request":
        p["pending_approvals"].append({"at": now(), "text": a.text, "state": "requested", "note": None})
        print(f"approval #{len(p['pending_approvals']) - 1} requested")
    else:
        try:
            item = p["pending_approvals"][int(a.text)]
        except (ValueError, IndexError):
            die("unknown approval index")
        item["state"] = "granted" if a.granted else "denied"
        item["note"], item["resolved_at"] = a.note, now()
        print(f"approval #{a.text} {item['state']}")
    save_progress(p)


def cmd_config(a: argparse.Namespace) -> None:
    p = load_progress()
    if a.key is None:
        print(json.dumps(p["config"], indent=2))
        return
    try:
        val = json.loads(a.value)
    except json.JSONDecodeError:
        val = a.value
    p["config"][a.key] = val
    save_progress(p)
    print(f"config {a.key} = {json.dumps(val)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("status"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_status)
    sp.add_parser("init").set_defaults(fn=cmd_init)
    sp.add_parser("sync").set_defaults(fn=cmd_sync)
    s = sp.add_parser("start"); s.add_argument("task"); s.set_defaults(fn=cmd_start)
    s = sp.add_parser("stage"); s.add_argument("task"); s.add_argument("stage", choices=STAGES); s.set_defaults(fn=cmd_stage)
    s = sp.add_parser("record"); s.add_argument("task")
    s.add_argument("--kind", required=True, choices=["developer", "tester", "reviewer", "orchestrator"])
    s.add_argument("--verdict", required=True,
                   choices=["COMPLETE", "PARTIAL", "BLOCKED", "PASS", "FAIL", "APPROVE", "REQUEST_CHANGES", "REJECT", "NOTE"])
    s.add_argument("--summary", required=True); s.add_argument("--evidence", action="append")
    s.set_defaults(fn=cmd_record)
    s = sp.add_parser("complete"); s.add_argument("task"); s.set_defaults(fn=cmd_complete)
    s = sp.add_parser("committed"); s.add_argument("task"); s.add_argument("--commit"); s.set_defaults(fn=cmd_committed)
    s = sp.add_parser("block"); s.add_argument("task"); s.add_argument("--reason", required=True); s.add_argument("--questions")
    s.set_defaults(fn=cmd_block)
    s = sp.add_parser("fail"); s.add_argument("task"); s.add_argument("--reason", required=True); s.set_defaults(fn=cmd_fail)
    s = sp.add_parser("reopen"); s.add_argument("task"); s.add_argument("--reason", required=True); s.set_defaults(fn=cmd_reopen)
    s = sp.add_parser("checkpoint"); s.add_argument("--note", required=True); s.set_defaults(fn=cmd_checkpoint)
    s = sp.add_parser("issue"); s.add_argument("text"); s.add_argument("--task"); s.set_defaults(fn=cmd_issue)
    s = sp.add_parser("approval"); s.add_argument("action", choices=["request", "resolve"]); s.add_argument("text")
    g = s.add_mutually_exclusive_group(); g.add_argument("--granted", action="store_true"); g.add_argument("--denied", action="store_true")
    s.add_argument("--note"); s.set_defaults(fn=cmd_approval)
    s = sp.add_parser("config"); s.add_argument("key", nargs="?"); s.add_argument("value", nargs="?"); s.set_defaults(fn=cmd_config)
    a = ap.parse_args()
    if a.cmd == "approval" and a.action == "resolve" and not (a.granted or a.denied):
        die("approval resolve needs --granted or --denied")
    a.fn(a)


if __name__ == "__main__":
    main()
