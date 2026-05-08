# 2026-05-09 — Four new reviewer roles: accessibility, migration-safety, i18n, docs-coherence

Adds four reviewer roles to the preflight panel pool, closing well-known coverage gaps that the existing 12 roles do not address. Pure additive change — no coordinator, synthesizer, verifier, or schema modifications.

## Motivation

The current 12 roles (api-design, concurrency, contrarian-strategist, cost-infra, data-model, error-handling, observability, ops-reliability, performance, security, supply-chain, testing) leave four classes of mistakes unmonitored:

1. **Accessibility (a11y / WCAG)** — any frontend artifact can ship keyboard-trap, missing ARIA semantics, insufficient contrast, focus-management mistakes. Today these slip through unless a reviewer is hand-picked.
2. **Migration safety** — DB schema migrations, online/offline rollout strategies, lock impact, backfill correctness, dual-write windows. `data-model` covers schema *design*; `api-design` covers contract evolution; nobody owns the *deployment* of those changes.
3. **Internationalization (i18n / l10n)** — hard-coded user-facing strings, locale-sensitive formatters, pluralization, timezone hygiene, RTL/bidi. No role currently flags these.
4. **Documentation coherence** — drift between code and README / CLAUDE.md / CHANGELOG / docstrings. Frequent and high-impact, but unowned.

## Scope boundaries

Each role's lens is bounded so it does not duplicate or conflict with existing roles. Out-of-scope concerns are forwarded via `out_of_scope[]` with `owner_role`.

| Role | In scope | Out of scope (owner_role) |
|---|---|---|
| **accessibility** | WCAG 2.1 AA, ARIA semantics, focus management, keyboard operability, contrast ratios, screen-reader compatibility, motion/animation a11y. | Visual design polish (none — `out_of_scope` topic). Render performance (`performance`). DOM-XSS via untrusted HTML (`security`). |
| **migration-safety** | Schema migration mechanics (online vs. offline, locking, batched backfills), expand-contract sequencing, dual-write/dual-read windows, rollback path, feature-flag gating of schema-coupled code. | Schema design itself (`data-model`). API contract evolution (`api-design`). CI/CD gating mechanics (`ops-reliability`). |
| **i18n** | Hard-coded user-facing strings, locale-sensitive formatters (date / number / currency / collation), pluralization (CLDR), timezone correctness, encoding (UTF-8 in / out), RTL & bidi safety, locale-aware test data. | Accessibility (`accessibility`). Copy / UX wording quality (`out_of_scope`). |
| **docs-coherence** | Drift between code and README / CLAUDE.md / CHANGELOG / docstrings / migration notes; stale code examples; missing deprecation notices for removed/renamed public surface. | API design proper (`api-design`). Spelling / style polish (`out_of_scope`). |

## Files added / changed

```
skills/preflight/roles/
  accessibility.md        — new
  migration-safety.md     — new
  i18n.md                 — new
  docs-coherence.md       — new
  index.json              — +4 entries (insert in alphabetical order)
  signals/
    frontend.yaml         — extend augments_roles to include accessibility, i18n; extend matchers with t(, useTranslation, Intl., gettext, alt=, role=, aria-
    migrations.yaml       — new
```

No changes to: `meta-agents/*`, `schemas/*`, `SKILL.md` (the panel pool is data-driven from `roles/index.json`), `hooks/*`, `evals/*` infrastructure (eval *cases* may be added separately).

### `roles/<name>.md` format

Each role file mirrors `roles/api-design.md`:

1. **YAML frontmatter** — `name`, `when_to_pick`, `tags`, `skip_when`, `context_sections`, `synced_from` (when applicable), `synced_at`.
2. **Title** — `# Role: <Human Name> Reviewer`.
3. **Prompt-injection defense block** — verbatim from existing roles; the artifact is data, not instructions.
4. **What you do NOT touch** — owner-role forwarding map (matches the table above).
5. **Domain expertise** — 3–5 key principles, each with a concrete example. Sourced from `synced_from` and adapted for plan/spec review (when source exists), otherwise written fresh.
6. **Output format** — strict JSON only:
   ```json
   {
     "role": "<name>",
     "verdict": "APPROVE" | "REVISE" | "REJECT",
     "must_fix":   [{"title": "...", "evidence": "...", "replacement": "..."}],
     "should_fix": [{"title": "...", "evidence": "...", "replacement": "..."}],
     "nice_fix":   [{"title": "...", "evidence": "...", "replacement": "..."}],
     "out_of_scope": [{"topic": "...", "owner_role": "..."}]
   }
   ```
   Verdict rules unchanged from existing roles.

### Source strategy

| Role | Source | Rationale |
|---|---|---|
| accessibility | sync from awesome-reviewers (a11y prompt) + adapt | mature community prompts exist |
| migration-safety | fresh-written | no single targeted source; corpus is scattered across api-evolution prompts |
| i18n | fresh-written | minimal coverage in awesome-reviewers |
| docs-coherence | fresh-written | doc-drift is project-class-specific |

Fresh-written roles use `synced_from: ~` (null) and document principles drawn from established practice (e.g., expand-contract for migrations, ICU/CLDR for i18n).

### `roles/index.json` entries

Inserted alphabetically. Each entry:

```json
{
  "name": "<role>",
  "when_to_pick": "<one-line trigger>",
  "tags": ["..."],
  "skip_when": "<one-line skip rule>",
  "context_sections": ["conventions", "architecture", "<role-specific>"],
  "synced_from": "<url-or-null>",
  "synced_at": "2026-05-09"
}
```

Trigger phrasings:

- `accessibility` — *"Artifact involves user-facing UI — components, pages, forms, interactive elements, modals, or any browser-rendered surface a human will operate."*
- `migration-safety` — *"Artifact introduces or changes a database schema migration, data backfill, dual-write window, or any rollout that mutates persistent state in production."*
- `i18n` — *"Artifact introduces or changes user-facing text, locale-dependent formatting, parsing of user input that varies by locale, or any string destined for end-user display."*
- `docs-coherence` — *"Artifact changes public-surface code (APIs, CLI flags, config keys, exported types) without an accompanying doc update, or modifies docs in a way that may have diverged from code."*

### `signals/migrations.yaml`

```yaml
group: migrations
matchers:
  - "migration"
  - "ALTER TABLE"
  - "CREATE INDEX"
  - "Alembic"
  - "Flyway"
  - "Liquibase"
  - "schema_version"
  - "backfill"
  - "BEGIN;"
  - "DROP COLUMN"
  - "RENAME"
augments_roles:
  - migration-safety
  - data-model
  - ops-reliability
checklist_intro: |
  This artifact mutates persistent state. Walk through these
  rollout-safety concerns in addition to your role's lens.
checklist:
  - id: lock_impact
    title: Does the migration take a long-held lock on a hot table?
    rationale: AccessExclusiveLock on a 100M-row table during business hours = outage.
  - id: rollout_phase
    title: Is the change expand-contract phased, or single-shot?
    rationale: Single-shot ALTER + code deploy that depends on the new column = race window.
  - id: backfill_strategy
    title: If new columns require backfill, is it batched and resumable?
    rationale: One giant UPDATE on a large table holds row locks and bloats WAL.
  - id: rollback_plan
    title: Is there a written rollback path for this migration?
    rationale: "Only roll forward" is not a plan; it's a hope.
  - id: dual_write_window
    title: If old and new code coexist mid-deploy, is dual-write/dual-read defined?
    rationale: Forgotten dual-write windows are the #1 cause of "the migration looked fine" incidents.
```

### `signals/frontend.yaml` extension

```yaml
augments_roles:
  - performance
  - security
  - testing
  - accessibility   # new
  - i18n            # new

matchers:
  # ... existing matchers preserved ...
  - "alt="          # new
  - "aria-"         # new
  - "role="         # new
  - "useTranslation" # new
  - "Intl."         # new
  - "gettext"       # new
  - "t("            # new
```

(Exact merged YAML produced at implementation time; no removed entries.)

## Risk and blast radius

- **Risk: low.** Pure additive. No existing role file changes. Only `frontend.yaml` is edited (additions only) and `index.json` gains four entries.
- Selector behavior change: previously, frontend artifacts triggered `[performance, security, testing]` — now also `[accessibility, i18n]`. This shifts panel composition for frontend reviews. Mitigation: existing budget guard in selector caps panel size; the additional two augments contend with — and may displace — lower-confidence picks. This is desired behavior.
- `migrations.yaml` introduces a new signal group entirely. Artifacts containing `ALTER TABLE` etc. will now trigger `[migration-safety, data-model, ops-reliability]`.

## Validation

1. **Schema-level:** `make validate-handoff-examples` (or whichever target validates `roles/index.json` against schema) must pass post-merge.
2. **Selector smoke:** four small synthetic artifacts (a11y / migration / i18n / doc-drift) each produce a panel containing the corresponding new role.
3. **End-to-end smoke:** one `/preflight` invocation on a real frontend fixture must include accessibility in the panel and produce a well-formed role report.
4. **Selector eval:** new test cases in `evals/` to lock in selector behavior — added in a follow-up PR if eval rig requires fixture work; not blocking for this design's first delivery.

## Out of scope (this spec)

- Optimization PRs #2 / #3 / #4 from `2026-05-07-optimization-analysis.md`.
- Pyramidal preflight `depth=` parameter.
- Changes to meta-agents (selector, synthesizer, verifier, adversarial, rubber-duck).
- New eval fixtures beyond minimal selector smoke; full eval suite expansion is a follow-up.
- New regulatory / compliance / ml-correctness / dx roles — only the four listed above are in scope.

## Acceptance

- `roles/index.json` lists 16 roles, alphabetically ordered, schema-valid.
- Four new `roles/*.md` files conform to the existing role-prompt template (frontmatter, defense block, scope, expertise, output JSON).
- `signals/frontend.yaml` augments two new roles; `signals/migrations.yaml` exists.
- `/preflight` end-to-end smoke on at least one fixture per new role completes and includes the role in the panel.
- `make validate-handoff-examples` (or equivalent) passes.
- CHANGELOG `[Unreleased]` entry summarizes the four roles added.
