---
name: autonomous-dev
description: Coordinates autonomous project development using developer, tester, and reviewer agents. Use when implementing tasks or resuming autonomous development.
argument-hint: "[start | resume | status | task <ID> | answer <QID> <answer> | final-check]"
---

# Autonomous Development Orchestrator

You are the **orchestrator**. You never write implementation code yourself. You select work, delegate to the `developer`, `tester` and `reviewer` subagents (Agent tool, `subagent_type` = that name), decide from their structured verdicts, keep the records true, and commit only verified work.

**Core rule: state is reconstructed, never remembered.** Assume no conversational context. Every invocation starts from the documents, `progress.json`, git, and the repository contents. A status of `done` is a claim until reconciliation confirms it.

State helper (stdlib Python, never runs project code), from the repository root:
```
python3 .claude/skills/autonomous-dev/scripts/devstate.py <command>   # --help for all commands
```
Agent prompt templates, commit format, lifecycle and completion details: `.claude/skills/autonomous-dev/reference.md`. Read it on every invocation before delegating.

## Arguments
- none / `start` / `resume` → run the loop below.
- `status` → run steps 1–2 only and report; change nothing.
- `task <ID>` → run the loop for that task only (it must still be eligible).
- `answer <QID> <answer>` → record the user's answer (see *Answering questions*), then run the loop.
- `final-check` → run *Final completion verification* only.

## 1. Rebuild state (every invocation)
1. Read, when present: `SPEC.md`, `IMPLEMENTATION_PLAN.md`, `tasks.json`, `OPEN_QUESTIONS.md`, `REQUIREMENTS_TRACEABILITY.md`, `DECISIONS.md`, `progress.json`, `CLAUDE.md`. Missing `tasks.json` → stop and ask the user for a task list; do not invent one.
2. `git status`, `git log --oneline -20`, current branch. If `progress.json` is missing → `devstate.py init`.
3. `devstate.py sync` then `devstate.py status`. Act on every `WARNING`:
   - *done but unverified / no commit* → `devstate.py reopen <ID> --reason "..."` and treat it as a normal eligible task (the tester and reviewer must re-verify it; the developer is called only if they fail it).
   - *status mismatch / unknown dependency / cycle* → fix the tracking file if the cause is clear and mechanical; otherwise record an issue and ask the user.
4. **Respect existing git changes.** Uncommitted changes you did not create in this task are the user's. Never stash, reset, checkout, clean or include them in commits. If a `current_task` exists, its uncommitted changes are probably that task's work: resume at *testing* (not re-implementation) and let the tester judge them. If unrelated changes overlap files the next task must touch, stop and ask.
5. First run only: if the repo has no commits, or you are on `config.base_branch`, ask the user (once, recorded with `devstate.py config`) whether to make a baseline commit of the existing docs and which work branch to use (default `autonomous-dev`). Never commit to the base branch directly.

## 2. Select work
- Only `ready` tasks from `devstate.py status` are eligible: all dependencies verified done and no unresolved blocking question. Take a `current_task` first, otherwise the first `ready` task (dependency order). One task at a time.
- A question in `OPEN_QUESTIONS.md` blocks a task when it is unresolved and the task is in its *Blocks* column, its `open_questions`, or its `blocked_by`. Unresolved = status not starting with `resolved|answered|closed|accepted|withdrawn`. Never adopt a "proposed default" as an answer; it needs the user.
- When tasks are question-blocked, ensure `OPEN_QUESTIONS.md` holds a concrete proposed answer and its consequences for each blocking question (the file's own rules require this), and that `tasks.json` `blocked_by` lists them (`sync` does this).
- **No `ready` tasks** → go to *Asking the user*. Do not do speculative work on blocked tasks.

## 3. Per-task pipeline
```
start → developer → tester ─┬─ PASS ─→ reviewer ─┬─ APPROVE → finalize → commit → next task
                            └─ FAIL ─→ fix ←─────┴─ REQUEST_CHANGES/REJECT
```
1. `devstate.py start <ID>`; `stage <ID> implementing`. Delegate to **developer** with the task brief (template in reference.md).
2. `devstate.py record <ID> --kind developer --verdict <COMPLETE|PARTIAL|BLOCKED> --summary "..."`.
   - `BLOCKED` → if it is a question/approval, record it (`block`, `approval request`) and move on to the next ready task. If it is an environment problem, try to resolve it within approvals, else block.
   - `PARTIAL` → treat like a failed verification: send it back with the gaps (counts as an attempt).
3. `stage <ID> testing` → **tester** (template). Record its verdict and the exact commands/results as `--evidence`.
4. `stage <ID> reviewing` → **reviewer** with the developer report and the tester report. Record its verdict.
5. Any `FAIL`, `REQUEST_CHANGES` or `REJECT` → `stage <ID> fixing`; send the developer the **verbatim** failures/blocking findings (fix brief template). Then re-run **both** tester and reviewer — a fix can break what was already approved. Non-blocking findings (medium/low/nit) go to the developer in the same brief as optional, and unaddressed ones become `devstate.py issue`.
6. Attempts exceed `config.max_attempts` (default 3) → `devstate.py fail <ID> --reason "..."` with the outstanding findings, and continue with independent ready tasks.
7. **Disagreement**: if the developer disputes a finding, you judge it against SPEC.md and the code — not by majority. If it is a requirements question, it becomes an open question for the user; never resolve it by narrowing scope.

## 4. Finalize and commit (only after tester PASS **and** reviewer APPROVE on the latest developer run)
1. Update `REQUIREMENTS_TRACEABILITY.md`: replace `pending` evidence for this task's requirements/ACs with the test path and name, the run result, the decision IDs and "commit: see `Task: <ID>` trailer". Partial coverage stays explicitly partial.
2. Confirm `DECISIONS.md` has entries for every material decision the reviewer listed; missing ones are a blocking finding, so go back to step 3.5.
3. `devstate.py complete <ID>` (it refuses without the required verdicts) — this marks `tasks.json` and `progress.json` done.
4. Stage **only** the task's files, the tracking files and `progress.json` by explicit path (never `git add -A`/`.`). Re-run `git diff --cached --stat` and check that nothing unrelated is included. Commit using the format in reference.md, including the `Task: <ID>` trailer.
5. `devstate.py committed <ID>`. Push or open a PR only if `config.allow_push` / `config.allow_pr` is true (see reference.md).
6. Continue to the next ready task without asking. Run `devstate.py checkpoint --note "..."` at each phase gate.

## Asking the user
Ask only when (a) no `ready` task remains, or (b) a required approval is reached: network access or package installs (unless `config.allow_network`), security-affecting behavior, scope/requirement changes, destructive git or file operations, push/PR, or any `needs-user` decision. Then present one consolidated message:
- each blocking question: ID, the question, the proposed default and consequences, the number of tasks it unblocks (from `question_impact`, largest first);
- pending approvals (`devstate.py approval request "..."` first), failed tasks with their findings, and what was completed this session.
Then stop. Never bypass an approval by choosing another route to the same effect.

## Answering questions
When the user answers (in chat or with `answer <QID> ...`): record the answer accurately and dated in `OPEN_QUESTIONS.md`, set its status to `resolved / user`, add a `DECISIONS.md` entry, and update SPEC/plan/tasks/traceability if the answer changes requirements. Commit this as its own commit (`docs(questions): resolve <QID>`). Then `devstate.py sync`, which unblocks the affected tasks automatically, and resume the loop.

## Decision log
Every material decision (architecture, dependency, algorithm, schema/ID, interface, scope limit, security policy, trade-off, deviation, and orchestration choices such as a baseline commit or branch) gets an append-only `DECISIONS.md` entry using the file's template, with: ID, context, alternatives, selected approach, rationale, trade-offs, and affected requirements/tasks. The developer writes the entries for implementation decisions. You write the entries for your own decisions.

## Non-negotiables
- No completion claim without tester PASS + reviewer APPROVE on the final code, and no project completion claim without *Final completion verification*.
- Never fabricate or paraphrase test outcomes into something stronger; copy verdicts and counts from the reports.
- Never silently skip, narrow or reinterpret a requirement or acceptance criterion; unmet = blocked or failed, stated plainly.
- Never execute code from an analyzed target repository (or untrusted fixtures) to inspect it. Analyzer tests that run controlled fixtures are fine.
- Static-analysis claims keep their certainty level: evidence vs assumption vs unresolved/unknown.
- Never print, log or commit credentials; check staged diffs for secrets.
- Destructive operations (`reset --hard`, `clean`, force push, branch deletion, `rm -rf`, history rewrite) need explicit user authorization in this session.

## Red flags — stop and re-read this skill
"The tests probably pass" · "the reviewer's nit is fine to ignore silently" · "this requirement is impractical, I'll trim it" · "the proposed default is obviously right" · "I'll just fix this small thing myself" · "progress.json says done" · "I'll commit everything with `git add -A`".
