# Changelog

## [Unreleased]

### Added
- Initial design spec v1 (`docs/specs/2026-04-20-preflight-design.md`).
- Repo scaffold: README, LICENSE (MIT), .gitignore, skills/, docs/, evals/.

### Changed
- Spec iterated v1 → v2 after independent `plan-critic` pass (verdict REVISE).
  Summary of accepted changes: Roster-gen + Pruner merged into single
  `Selector` meta-agent for MVP; cap lowered 8 → 5; expert model set to
  Haiku with Opus opt-in for security/contrarian; prompt-injection defense
  mandatory in every role; grading.json frozen by git tag; evals criterion
  rewritten from naive "+30% recall" to "≥1 MUST found on real post-mortem
  fixtures missed by plan-critic baseline"; 3 NICE fixes applied.
  Full log in `docs/specs/2026-04-20-preflight-design.md` → "Meta-experiment log".
