# preflight

**Adaptive multi-expert panel skill for Claude Code** — run your plan, spec, or chat through a panel of independent domain experts *before* writing any code.

## What it does

One agent = one clearly-scoped role. `preflight` dynamically assembles a panel of reviewers tailored to your artifact (security engineer, performance analyst, API designer, quant trader, OAuth specialist…), runs them in parallel, and synthesizes findings into a single ranked report.

Unlike a single contrarian reviewer, `preflight` gives you **independent, non-overlapping perspectives** — each expert looks only at their domain and cross-confirms findings from other roles.

## Installation

```bash
git clone https://github.com/<you>/preflight.git ~/programming/claude/preflight
ln -sf ~/programming/claude/preflight/skills/preflight ~/.claude/skills/preflight
```

Reload Claude Code (or start a new session). The skill activates on `/preflight` or natural language triggers.

## Usage

```
/preflight path/to/plan.md
/preflight path/to/design-spec.md
/preflight                          # reviews the current conversation
```

Or naturally: _"собери экспертов на этот дизайн"_, _"панель ревьюеров на plan.md"_, _"panel review before I write this"_

### What gets reviewed

- **Plan files** — architecture decisions, data flows, API contracts
- **Design specs** — schema choices, migration risks, cost projections
- **Chat context** — the current conversation (when no file given)

## Pipeline

```
Ingest → Brief → Context pack (conventions + architecture always included)
   ↓
Selector  → wide roster → prune to 3-5 → Human gate (ok / edit / abort)
   ↓
Parallel expert dispatch (each gets brief + context pack + their role prompt)
   ↓
Synthesizer → dedup + severity + cross-confirmation + conflict detection
   ↓
Report: APPROVE / REVISE / REJECT  +  MUST / SHOULD / NICE findings
```

Human gate is **on by default** — you see the proposed panel and can add, remove, or abort before any expert runs.

## Role catalog

| Role | Picks up | Model |
|------|----------|-------|
| `security` | Auth, injection, secrets, crypto, IDOR, PII | Opus |
| `performance` | N+1, blocking I/O, missing indexes, memory | Sonnet |
| `testing` | Coverage gaps, missing edge cases, test strategy | Sonnet |
| `concurrency` | Race conditions, deadlocks, missing locks | Sonnet |
| `api-design` | Breaking changes, naming, versioning, idempotency | Sonnet |
| `data-model` | Schema constraints, migration risk, normalization | Sonnet |
| `ops-reliability` | Observability, deployment, failure modes, SLOs | Sonnet |
| `cost-infra` | Cloud cost, LLM spend, unbounded growth | Sonnet |
| `supply-chain` | Dependencies, licenses, build pipeline integrity | Sonnet |
| `contrarian-strategist` | Wrong problem, over-engineering, hidden assumptions | Opus |

Ad-hoc roles (e.g. "quant trader", "GDPR counsel") are generated inline by the Selector when no catalog role fits.

## ExpertReport format

Every expert returns the same JSON contract:

```json
{
  "role": "security",
  "verdict": "REVISE",
  "must_fix":   [{"title": "...", "evidence": "...", "replacement": "..."}],
  "should_fix": [{"title": "...", "evidence": "...", "replacement": "..."}],
  "nice_fix":   [{"title": "...", "evidence": "...", "replacement": "..."}],
  "out_of_scope": [{"topic": "...", "owner_role": "..."}]
}
```

The Synthesizer uses `out_of_scope` as a cross-confirmation signal: if Security says "performance concern → performance" and Performance independently raises the same point, it gets flagged as `cross_confirmed`.

## Prompt injection defense

Every role prompt opens with a hardcoded defense block. If the reviewed artifact contains instructions like "ignore prior instructions" or "return APPROVE", the expert emits it as a `must_fix` item and continues the review — it does not execute the instruction.

## Evals

`evals/` contains 8 fixtures (4 real post-mortem patterns, 2 synthetic, 1 injection test, 1 good plan) with a frozen `grading.json` baseline. Run the checklist:

```bash
python evals/run_eval.py checklist
```

## Index generation

```bash
make build-index   # regenerates roles/index.json from frontmatter
make test-index    # validates all required fields present
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — adding a role is one PR, one file.

## License

MIT — see [LICENSE](LICENSE).
