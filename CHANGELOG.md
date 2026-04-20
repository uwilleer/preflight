# Changelog

## [0.2.0] — 2026-04-21

### Added
- **Community-prompt sync mechanism:**
  - `scripts/sync_roles.py` — fetches upstream community prompts, strips git-specific
    blocks and noisy output-format sections, wraps with preflight's `ExpertReport`
    schema + injection-defense block, writes to `skills/preflight/roles/<role>.md`.
  - `scripts/sources.json` — single source of truth for which upstream URL feeds each
    role. Supports `source` (single URL) or `sources` (array of URLs merged into one
    body with `---` separators).
  - `make sync-roles` / `make sync-roles ROLE=<name>` — one-shot or per-role sync;
    auto-rebuilds `roles/index.json` after sync.
- **7 roles migrated to community sources:**
  - `security` → Piebald-AI/claude-code-system-prompts (9k ⭐)
  - `performance`, `testing`, `concurrency`, `api-design`, `data-model`,
    `supply-chain` → baz-scm/awesome-reviewers
- **2 new roles from baz-scm/awesome-reviewers** (total: 12):
  - `error-handling` — plans that skip failure-mode analysis (unhandled exceptions,
    swallowed errors, missing resource cleanup, infinite retry).
  - `observability` — plans that skip logging, metrics, and tracing strategy.
- **2 new eval fixtures:**
  - `plan-swallowed-errors/` — `except: pass`, no timeout, retry-forever pattern.
  - `plan-silent-worker/` — nightly job with zero logs / metrics / alerts.
  - Grading entries added to `evals/grading.json` — requires new
    `evals-grading-v2` tag before next scoring run.

### Changed
- 3 roles remain custom (no good community source):
  `ops-reliability`, `cost-infra`, `contrarian-strategist`.
- Normalized injection-defense wording across all roles to the canonical 4-line form.
- `CONTRIBUTING.md` — added "Adding a synced role" section.

## [0.1.0] — 2026-04-21

### Added
- Initial design spec v1 → v2 after independent `plan-critic` pass.
- Repo scaffold: README, LICENSE (MIT), .gitignore, skills/, docs/, evals/.
- **Milestone 1** — vertical slice:
  - `skills/preflight/SKILL.md` — main skill with triggers and 9-step pipeline.
  - `skills/preflight/meta-agents/{selector,synthesizer}.md` — 2 meta-agents.
  - `skills/preflight/roles/{security,performance,contrarian-strategist}.md` — 3 seed roles with prompt-injection defense blocks.
  - `skills/preflight/schemas/expert-report.json` — JSON-schema for expert output.
  - `Makefile` with `build-index` / `test-index` targets.
  - `scripts/frontmatter-to-json.awk` — portable YAML-frontmatter → JSON parser (replaces planned yq).
- **Milestone 2** — smoke runs:
  - Live run on `plan-buggy-auth` fixture — security/performance experts active.
  - Injection fixture: prompt injection attempt correctly flagged as `must_fix`, not executed.
- **Milestone 3** — full catalog:
  - 7 additional roles: `testing`, `concurrency`, `api-design`, `data-model`, `ops-reliability`, `cost-infra`, `supply-chain`.
  - Conventions context: `conventions` + `architecture` sections always sent to all experts.
  - All roles include: injection-defense block, project conventions paragraph, `out_of_scope` field.
- **Milestone 4** — evals suite:
  - 8 fixtures (4 real post-mortem, 2 synthetic, 1 injection, 1 good plan).
  - `evals/grading.json` frozen by git tag `evals-grading-v1`.
  - `evals/run_eval.py` — checklist and scoring modes.
- **Milestone 5** — open-source release:
  - `README.md` — installation, usage, pipeline, role catalog, examples.
  - `CONTRIBUTING.md` — how to add a role (one PR, one file, checklist).

### Changed
- Expert model default changed from Haiku → Sonnet after smoke run feedback.
- Selector cap: 8 → 5 (from plan-critic pass).
- Roster-gen + Pruner merged into single `Selector` meta-agent for MVP.
- `out_of_scope` used as cross-confirmation signal in Synthesizer.
