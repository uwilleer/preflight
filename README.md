# preflight

**Adaptive multi-expert panel skill for Claude Code** — run your plan, spec, or design-chat through a panel of independent experts of different professions **before** you write any code.

> Status: **WIP**. Not yet ready for general use. First open-source release planned after Milestone 4 (evals suite).

## Idea

One agent = one clearly-scoped role. The skill dynamically assembles a panel of experts tailored to your task (security, performance, testing, domain-specific like "quant trader" or "OAuth specialist"…), runs them in parallel on your artifact, and synthesizes their findings into a single actionable report with severity ranking and conflict highlighting.

Unlike a single contrarian reviewer (`plan-critic`) or undifferentiated parallel dispatch (`dispatching-parallel-agents`), `preflight` is a **multi-perspective pre-write review** — targeted at catching bugs, blind spots, and bad decisions *before* they're encoded in a commit.

## Pipeline (9 steps)

```
Ingest → Brief → Context decide → [Context pack, sectioned by role tags]
   ↓
Selector (chosen 3-5 + dropped)   →  [Human gate — visible default in MVP]
   ↓
Parallel dispatch (N experts; Haiku by default, Opus for security/contrarian)
   ↓
Synthesizer (dedupe + severity + conflicts + out_of_scope cross-confirmation)
   ↓
Report (APPROVE / REVISE / REJECT + actionable list)
```

## Status

- [x] Design spec v1 — `docs/specs/2026-04-20-preflight-design.md`
- [x] Independent `plan-critic` pass → REVISE → spec v2 iterated
- [x] Meta-agents (`selector`, `synthesizer`)
- [~] Base role catalog — 3/10 seed roles with prompt-injection defense
- [ ] First live run on a buggy-plan fixture + injection fixture
- [ ] Evals suite vs `plan-critic` baseline (grading.json frozen by git tag)
- [ ] Open-source release (v0.1.0)

## Design

See [`docs/specs/2026-04-20-preflight-design.md`](docs/specs/2026-04-20-preflight-design.md) for the full design document.

## License

MIT — see [LICENSE](LICENSE).
