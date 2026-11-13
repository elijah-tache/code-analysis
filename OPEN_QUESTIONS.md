# OPEN_QUESTIONS.md

Every question has an ID, owner, status, impact, default/proposal, and resolution evidence. Claude must update this file and `DECISIONS.md` when resolved. Do not invent answers. `needs_user` blocks only the identified dependent tasks; other tasks continue.

| ID | Question | Status / owner | Proposed default | Blocks |
|---|---|---|---|---|
| Q01 | Which Python syntax versions are officially supported for parsing and environment modeling? | resolved / user (2026-11-12) | Start Python 3.10–3.13 syntax; treat newer syntax as diagnostic; test parser behavior per runtime | T002, T006 |
| Q02 | Is the core product CLI + graph API sufficient for Stage 1, or is a browser visualization mandatory? | resolved / user (2026-11-12) | Core CLI/API mandatory; lightweight browser viewer optional until performance gates pass | T027 |
| Q03 | What is the expected project scale and reference machine for hard performance gates? | resolved / user (2026-11-12) | Benchmark 10k files / ~1M LOC; publish hardware and observed values | T028 |
| Q04 | Which package managers/lockfile dialects must be complete in v1? | resolved / user (2026-11-12) | pyproject, requirements, installed metadata first; lockfiles via independent adapters with diagnostics | T017, T018 |
| Q05 | May the engine perform opt-in network metadata sync, or must all operation remain air-gapped? | resolved / user (2026-11-12) | Offline by default, optional metadata import from local snapshots; network fetch not required | T019, T021 |
| Q06 | What are the exact compatibility targets (OS, ABI, architecture, extras, dependency groups)? | resolved / user (2026-11-12) | Model explicit environment tuple; default current platform only if stated by user | T016, T020 |
| Q07 | Are commercial/open-source license constraints imposed on parsers, type engines, graph libraries or metadata? | resolved / user (2026-11-12) | Prefer permissive libraries; document licenses and alternatives | T003 |
| Q08 | What should count as a breaking change vs a potential impact? | resolved / user (2026-11-12) | Evidence-backed categories: certain structural incompatibility, likely, possible, unknown | T025 |
| Q09 | Should first release support cross-repository graphs or only multi-package monorepos? | resolved / user (2026-11-12) | One workspace with multiple local packages; cross-repo deferred | T001, T007 |
| Q10 | Are pre-existing `.pyi` stubs and local wheel artifacts available for version-specific API analysis? | resolved / user (2026-11-12) | Analyze supplied artifacts; report unknown if absent | T019, T020 |
| Q11 | Should source content be stored in the graph, or only locations/hashes and short evidence excerpts? | resolved / user (2026-11-12) | Locations/hashes plus minimal redacted excerpts; never secrets | T004, T022 |
| Q12 | Is local HTTP API acceptable, and what access controls are needed? | resolved / user (2026-11-12) | Loopback-only, read-only, disabled unless enabled | T026 |
| Q13 | Which license applies to the project itself (affects LICENSE file, package metadata, redistribution/PyPI publication)? | open / needs_user | MIT (alternatives: Apache-2.0, BSD-3-Clause, proprietary); see D-0037 | T031, T032 |
| Q14 | The repository lives under iCloud Drive (`~/Desktop`), which re-hides the editable `.pth` file so `make install` cannot be durable there. Move the repository out of iCloud, keep it but place the venv outside (`make VENV=~/.venvs/code-analysis install`), or leave both and accept that only the pytest/`PYTHONPATH=src` paths work? | open / needs_user | Option 2 (venv outside iCloud) is the least disruptive and already supported; see D-0040 | none (tests do not depend on the install); affects local use of the `code-analysis` console script |

## Claude autonomy rules
Claude may independently decide reversible internal design details after comparing alternatives and recording them in `DECISIONS.md`. Claude must not assume an unanswered product/security/environment requirement is approved. For each blocked task, add `blocked_by` question IDs in `tasks.json`, write a concrete proposed answer and its consequences here, and continue unrelated tasks. When the user answers, record the answer verbatim or accurately paraphrased, date it, mark resolved, log decision, and re-evaluate task dependencies. If an answer changes requirements, update spec, plan, task definitions and traceability in one coherent commit.

## Resolutions

Answers given by the user on 2026-11-12 (chat), recorded verbatim or closely paraphrased. Decision entries D-0002–D-0013.

- **Q01** — resolved 2026-11-12 by user: Support Python 3.8–3.14 syntax. (D-0002)
- **Q02** — resolved 2026-11-12 by user: Browser viewer is not mandatory. (D-0003)
- **Q03** — resolved 2026-11-12 by user: Use proposed default (10k files / ~1M LOC; publish hardware and observed values). (D-0004)
- **Q04** — resolved 2026-11-12 by user: Use proposed default (pyproject, requirements, installed metadata first; lockfiles via independent adapters with diagnostics). (D-0005)
- **Q05** — resolved 2026-11-12 by user: Use proposed default (offline by default; optional local metadata snapshot import; network fetch not required). (D-0006)
- **Q06** — resolved 2026-11-12 by user: Use proposed default (explicit environment tuple; default current platform only if stated by user). (D-0007)
- **Q07** — resolved 2026-11-12 by user: Use proposed default (prefer permissive libraries; document licenses and alternatives). (D-0008)
- **Q08** — resolved 2026-11-12 by user: Categories: certain / possible / unknown (no separate "likely" category). (D-0009)
- **Q09** — resolved 2026-11-12 by user: Start with a single repository containing multiple packages, designed with the option to scale to cross-repository graphs later. (D-0010)
- **Q10** — resolved 2026-11-12 by user: Use proposed default (analyze supplied artifacts; report unknown if absent). (D-0011)
- **Q11** — resolved 2026-11-12 by user: Choose whatever is faster to navigate, not faster to create (optimize the read/query path over index build time). (D-0012)
- **Q12** — resolved 2026-11-12 by user: Local HTTP API is acceptable (loopback-only, read-only, disabled unless enabled). (D-0013)

- **Q13** — opened 2026-11-12 by Claude (T003): project license undecided; no license is claimed in package metadata until answered (D-0037).
- **Q14** — opened 2026-11-13 by Claude (T003 fix round, tester finding F1): iCloud Drive hides the editable `.pth` file within seconds of `make install`; `make install` now fails honestly on this host with the options; the user's choice decides the local layout (D-0040).

All dependent tasks were re-evaluated with `devstate.py sync` after these resolutions.
