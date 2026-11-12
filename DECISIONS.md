# DECISIONS.md — Single authoritative decision log

**Mandatory rule:** Claude must record **every material decision it makes** here, including architecture, dependencies, parsing strategies, scope limits, schema/ID choices, resolution algorithms, uncertainty classification, version sources, performance compromises, security policies, and changes to requirements. No undocumented “obvious” decisions. Small routine coding details can be grouped per task, but any choice affecting behavior, interface, correctness, or maintenance needs an entry. This file is append-only: supersede rather than silently edit earlier entries. Do not confuse proposals with approved decisions.

## Decision entry template

### D-0001 — [short title]
- Date (UTC): YYYY-MM-DD
- Status: proposed | accepted | superseded | rejected | needs-user
- Author/approver: Claude / user where relevant
- Related: requirement IDs, task IDs, question IDs, commits
- Context/problem: ...
- Options considered: ... (at least two meaningful options where feasible)
- Chosen option: ...
- Rationale/evidence: ...
- Tradeoffs, risks, limitations: ...
- Consequences and follow-up work: ...
- Verification: test IDs, benchmark evidence, code references or pending
- Supersedes: D-... (if applicable)

## Initial baseline decisions to validate
These are **proposals**, not silent implementation approvals. Claude must explicitly accept/modify each relevant proposal in numbered entries before implementing it.

- B01: Non-executing, offline-first source analysis with no AI.
- B02: Typed provenance graph with uncertainty and environment-specific edges.
- B03: SQLite-backed indexed persistence behind an adapter as the initial candidate.
- B04: AST-driven core with optional syntax/token or stub support.
- B05: Deterministic snapshots, bounded traversals, no whole-graph render.
- B06: Local versioned artifacts required for claims about third-party API availability; absent evidence is `unknown`.
- B07: User approval required for external network access, security-affecting behavior, and changes to release scope.

## Decision entries

<!-- Claude appends D-0001, D-0002, ... here. -->

### D-0001 — Git branching model and baseline commit
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (workflow specified in the Stage 1 kickoff instruction) / Claude (orchestrator)
- Related: all tasks; IMPLEMENTATION_PLAN.md "Workflow protocol" step 5
- Context/problem: The repository had a remote (`origin`) but no commits, no `.gitignore` and no branch structure. The autonomous workflow needs a stable branch, an integration branch and isolated per-task branches, plus a committed baseline of the planning documents so that later diffs are reviewable.
- Options considered: (a) single `main` with feature branches; (b) `main` (stable) + `dev` (integration) + `feature/<task-id>-<description>` branches merged into `dev` with non-fast-forward merges, `dev` merged into `main` only on user-approved release; (c) trunk-based with direct commits to `main`.
- Chosen option: (b), as specified by the user.
- Rationale/evidence: Keeps `main` releasable, retains per-task history through merge commits, and matches the user's explicit instruction. A baseline commit on `main` containing only the planning documents, agent/skill configuration and `.gitignore` is required before `dev` can be created without rewriting history.
- Tradeoffs, risks, limitations: Merge commits add history noise; conflicts must be resolved on the feature branch and re-tested before merging. No push/PR until the user authorizes remote operations (`progress.json` config `allow_push`/`allow_pr`, default false).
- Consequences and follow-up work: Every verified task is committed on its feature branch with a `Task: <ID>` trailer and merged `--no-ff` into `dev`; merged local feature branches are deleted after the merge. `progress.json` config records `base_branch: dev`, `stable_branch: main`.
- Verification: `git log --graph` on `dev` after the first task merge; `devstate.py status` reports the task's commits reachable from `dev`.
- Supersedes: none
