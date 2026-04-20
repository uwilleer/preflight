# Changelog

## [Unreleased]

### Added
- Initial design spec v1 (`docs/specs/2026-04-20-preflight-design.md`).
- Repo scaffold: README, LICENSE (MIT), .gitignore, skills/, docs/, evals/.
- Milestone 1 — vertical slice:
  - `skills/preflight/SKILL.md` — main skill with triggers and 9-step pipeline.
  - `skills/preflight/meta-agents/{selector,synthesizer}.md` — 2 meta-agents.
  - `skills/preflight/roles/{security,performance,contrarian-strategist}.md` —
    3 seed roles with prompt-injection defense blocks.
  - `skills/preflight/schemas/expert-report.json` — JSON-schema for expert output.
  - `Makefile` with `build-index` / `test-index` targets.
  - `scripts/frontmatter-to-json.awk` — portable YAML-frontmatter → JSON parser
    (replaces planned yq dependency with awk+jq to avoid an extra brew install).
  - `skills/preflight/roles/index.json` — generated (3 roles, validated).

### Changed
- Spec iterated v1 → v2 after independent `plan-critic` pass (verdict REVISE).
  Summary of accepted changes: Roster-gen + Pruner merged into single
  `Selector` meta-agent for MVP; cap lowered 8 → 5; expert model set to
  Haiku with Opus opt-in for security/contrarian; prompt-injection defense
  mandatory in every role; grading.json frozen by git tag; evals criterion
  rewritten from naive "+30% recall" to "≥1 MUST found on real post-mortem
  fixtures missed by plan-critic baseline"; 3 NICE fixes applied.
  Full log in `docs/specs/2026-04-20-preflight-design.md` → "Meta-experiment log".
