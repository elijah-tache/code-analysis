# autonomous-dev reference

## Agent briefs
Subagents start with **no context**. Each brief must stand alone. Fill in every `<...>`; paste requirement text and acceptance criteria verbatim from the source documents rather than summarizing them.

### Developer — new task
```
Task <ID> — <title> (phase <P>)
Attempt <n> of <max>.

Description: <tasks.json description, verbatim>
Requirements: <R-IDs with their definitions from REQUIREMENTS_TRACEABILITY.md>
Acceptance criteria: <AC-IDs with their full text from SPEC.md §10>
Deliverables: <tasks.json deliverables>
Verification expected: <tasks.json verification>
Relevant spec sections: <SPEC.md section numbers and titles to read>
Relevant prior decisions: <D-IDs>
Dependencies already done: <IDs + one-line summary of what each provides, files>
Resolved questions affecting this task: <QID: answer>
Approvals in force: network=<config.allow_network>; anything else the user granted
Pre-existing uncommitted changes you must not touch: <paths or "none">

Implement this task. Return the Developer Report defined in your instructions.
```

### Developer — fix
```
Task <ID> — fix round, attempt <n> of <max>. Your previous report: <paste>.
Blocking findings to fix (verbatim):
<tester failures F#, reviewer findings R# with severity>
Optional, non-blocking findings: <list>
Do not change scope or requirements to resolve findings. If you believe a finding is wrong, say so with evidence in your report instead of working around it.
Return the Developer Report.
```

### Tester
```
Verify task <ID> — <title>.
Acceptance criteria: <full text>
Requirements: <R-IDs + text>
Verification expected by tasks.json: <...>
Developer report (claims to verify, not evidence): <paste>
Files changed according to git: <git status --porcelain / git diff --stat>
Pre-existing changes unrelated to this task: <paths or none>
Project safety boundaries: <e.g. SPEC.md §3: never execute analyzed target code>
Run focused tests, the full regression suite, type checks and lint. Return the Tester Report.
```

### Reviewer
```
Review task <ID> — <title>.
Acceptance criteria and requirements: <full text>
Relevant SPEC.md sections and architecture: <sections; IMPLEMENTATION_PLAN.md architecture line>
Diff to review: run `git diff` (plus untracked files: <list>)
Developer report: <paste>
Tester report: <paste>
Decisions added in this task: <D-IDs>
Return the Reviewer Report.
```

Parse only the fixed verdict lines (`Status:` / `Verdict:`). If a report has no recognizable verdict, re-ask that agent once for the report in the required format. If it still has none, treat it as FAIL.

## Commit format
```
<type>(<scope>): <imperative summary, ≤72 chars>

<what changed and why; 2–6 lines>

Verification: <tester commands + counts>; review: APPROVE
Decisions: D-00xx, D-00yy
Task: T0NN
Requirements: R0x, AC-0y
<attribution lines required by the environment, if any>
```
`type` ∈ feat, fix, test, docs, refactor, build, ci, chore. The `Task:` trailer is mandatory: `devstate.py` uses it to find a task's commits, and to keep working after rebases or squashes. Commits that only change tracking files use `chore(progress): ...`.

## Lifecycle coverage (inside the same pipeline; no separate skills)
| Concern | How it is handled |
|---|---|
| Unit / integration tests | Developer writes them per task. The tester runs the focused tests, then integration tests. |
| Regression | The tester runs the full suite on every round. A new failure or skip anywhere is a FAIL. |
| CI | When a task delivers CI config, the tester runs each CI step locally (same commands). Remote CI is verified only if pushing is authorized: push, then poll the run (`gh run watch` if `gh` exists). Without push it is reported as "locally verified, remote unverified", never as passing. |
| Docker | Only when a task or spec requires it. The tester runs `docker build`, plus a smoke run of the analyzer image on a controlled fixture. If Docker is not installed, the task is BLOCKED (environment), not passed. |
| Docs / README | Developer updates docs touched by behavior changes in the same task. The reviewer checks that the docs match the behavior. |
| Review feedback / fixes / recommits | Fix loop in SKILL.md §3.5. Each fix round is re-tested and re-reviewed before a single commit for the task. Feedback found after a task was committed reopens it (`reopen`) and gets its own `fix(...)` commit with the same `Task:` trailer. |
| Pull requests | Only if `config.allow_pr` is true and a remote exists. Push the work branch (needs `allow_push`), then open a PR against `config.base_branch` with a body listing tasks, verification and decisions. Never merge it yourself. |
| Phase gates | When the last task of a phase is done, run the full suite and the phase gate checks from IMPLEMENTATION_PLAN.md through the tester (brief: the gate text as acceptance criteria). Run `checkpoint`. A failed gate opens an issue and blocks the next phase's tasks (`block`). |

## progress.json fields (maintained by devstate.py)
`config` (base_branch, work_branch, max_attempts, allow_push, allow_pr, allow_network, baseline_commit_approved) ·
`current_task` {id, stage, attempt, started_at} ·
`tasks.<ID>` {status, attempts, stage, blocked_reason, blocking_questions, commits, evidence, history[{at, kind, verdict, summary, evidence}], completed_at} ·
derived on `sync`: `completed`, `ready`, `blocked` [{task, reasons, questions}], `outstanding`, `question_impact`, `warnings`, `git`, `last_reconciled_at` ·
`open_issues`, `pending_approvals` [{text, state, note}], `last_checkpoint` {at, task, commit, note}.

Edit it only through `devstate.py`. It writes atomically (temp file + fsync + rename). A task counts as **verified done** only if its history shows tester PASS and reviewer APPROVE after its last developer run, *and* a commit with its `Task:` trailer is reachable from HEAD.

## Final completion verification
Run this when `status` reports no ready, blocked or outstanding tasks (or when `final-check` is invoked):
1. `devstate.py status` reports `project complete: YES`. That requires: every task verified done, no unresolved questions, no requested approvals, and a clean tree.
2. Fresh full verification through the **tester**: the full test suite, type check, lint, CI steps locally, the Docker build if required, and every acceptance criterion in SPEC.md, each mapped to evidence.
3. Whole-project **reviewer** pass: SPEC compliance across all ACs, `REQUIREMENTS_TRACEABILITY.md` has no `pending` rows, `DECISIONS.md` is complete and append-only, and the docs match the behavior.
4. Only if both pass: write the completion report, using the template in IMPLEMENTATION_PLAN.md when one exists, as a commit, and tell the user. Otherwise report precisely what fails. The project is not complete.
