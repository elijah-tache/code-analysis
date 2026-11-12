# OPEN_QUESTIONS.md

Every question has an ID, owner, status, impact, default/proposal, and resolution evidence. Claude must update this file and `DECISIONS.md` when resolved. Do not invent answers. `needs_user` blocks only the identified dependent tasks; other tasks continue.

| ID | Question | Status / owner | Proposed default | Blocks |
|---|---|---|---|---|
| Q01 | Which Python syntax versions are officially supported for parsing and environment modeling? | open / needs_user | Start Python 3.10–3.13 syntax; treat newer syntax as diagnostic; test parser behavior per runtime | T002, T006 |
| Q02 | Is the core product CLI + graph API sufficient for Stage 1, or is a browser visualization mandatory? | open / needs_user | Core CLI/API mandatory; lightweight browser viewer optional until performance gates pass | T027 |
| Q03 | What is the expected project scale and reference machine for hard performance gates? | open / needs_user | Benchmark 10k files / ~1M LOC; publish hardware and observed values | T028 |
| Q04 | Which package managers/lockfile dialects must be complete in v1? | open / needs_user | pyproject, requirements, installed metadata first; lockfiles via independent adapters with diagnostics | T017, T018 |
| Q05 | May the engine perform opt-in network metadata sync, or must all operation remain air-gapped? | open / needs_user | Offline by default, optional metadata import from local snapshots; network fetch not required | T019, T021 |
| Q06 | What are the exact compatibility targets (OS, ABI, architecture, extras, dependency groups)? | open / needs_user | Model explicit environment tuple; default current platform only if stated by user | T016, T020 |
| Q07 | Are commercial/open-source license constraints imposed on parsers, type engines, graph libraries or metadata? | open / needs_user | Prefer permissive libraries; document licenses and alternatives | T003 |
| Q08 | What should count as a breaking change vs a potential impact? | open / Claude proposes, user approves | Evidence-backed categories: certain structural incompatibility, likely, possible, unknown | T025 |
| Q09 | Should first release support cross-repository graphs or only multi-package monorepos? | open / needs_user | One workspace with multiple local packages; cross-repo deferred | T001, T007 |
| Q10 | Are pre-existing `.pyi` stubs and local wheel artifacts available for version-specific API analysis? | open / needs_user | Analyze supplied artifacts; report unknown if absent | T019, T020 |
| Q11 | Should source content be stored in the graph, or only locations/hashes and short evidence excerpts? | open / needs_user | Locations/hashes plus minimal redacted excerpts; never secrets | T004, T022 |
| Q12 | Is local HTTP API acceptable, and what access controls are needed? | open / needs_user | Loopback-only, read-only, disabled unless enabled | T026 |

## Claude autonomy rules
Claude may independently decide reversible internal design details after comparing alternatives and recording them in `DECISIONS.md`. Claude must not assume an unanswered product/security/environment requirement is approved. For each blocked task, add `blocked_by` question IDs in `tasks.json`, write a concrete proposed answer and its consequences here, and continue unrelated tasks. When the user answers, record the answer verbatim or accurately paraphrased, date it, mark resolved, log decision, and re-evaluate task dependencies. If an answer changes requirements, update spec, plan, task definitions and traceability in one coherent commit.
