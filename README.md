# preflight

**Multi-expert panel skill for Claude Code.** Run your plan, spec, or RFC through 3-5 independent domain experts in parallel — *before* writing any code. Get a single ranked report with verdict, MUST-FIX items, and decision cards.

## What you actually get

Sample output for a `users`-table sharding plan:

```markdown
## Preflight — docs/specs/2026-shard-users.md

**Вердикт:** REVISE — два MUST-FIX и одно решение по миграционному окну.

### Что обязательно поправить до кода (2)
- L42 — миграция блокирует записи на ~14 мин: `ALTER TABLE users SHARD KEY`
  берёт ACCESS EXCLUSIVE на 50M строк
  → split в две транзакции через `pg_repack`, либо feature-flag + dual-write период
  <sub>подтвердили: data-model, ops-reliability</sub>
- L78 — `user_id` в 4 downstream-сервисах хардкодится как int64; новый shard-id формат сломает
  → compatibility-shim (старый int64 → composite) на gateway до миграции
  <sub>подтвердили: api-design, data-model</sub>

### Решения, которые нужно принять вам (1)
**Когда выполнять миграцию: maintenance vs blue-green?**
- A) 30-min maintenance окно в воскресенье — простой downtime, 503 на 30 мин
- B) Blue-green dual-write на 2 недели — без downtime, +$1.8k инфра, риск split-brain при rollback

Компромисс: операционная сложность + cost vs UX и риск отката.
**Рекомендация:** A — brief называет «cost-conscious» как success criterion;
30 мин downtime укладывается в SLA 99.5% (3.6 ч/мес).

### Не закрытые вопросы (1)
- Стратегия rollback при partial-shard failure — никто не разобрал,
  хотя ops-reliability отметил это как data-model concern.

<details>
<summary>Панель и отфильтрованное (5 экспертов, 4 отброшено как шум)</summary>
...
</details>
```

Three things to notice:
- **Cross-confirmation** (`<sub>подтвердили: ...`) — independently raised by ≥2 roles, higher confidence.
- **Decision cards** with explicit recommendation traceable to the brief — not "consider X".
- **Untouched concerns** — gaps in panel coverage that single-reviewer tools fundamentally cannot produce.

## Why this vs single-reviewer alternatives

- **Plan-critic** (one contrarian) misses domain-specific blind spots — security ≠ performance ≠ data-model expertise.
- **Code review tools** are post-write — preflight catches the same issues at plan stage, when fixing them costs minutes instead of days.
- **"Just think harder yourself"** — you can't simulate 5 independent perspectives in your own head; you confirm your own bias.

## Numbers that matter

- **12 catalog roles** + ad-hoc domain roles generated inline by the Selector when no catalog role fits.
- **~25k main-session context per run** — three-phase sub-coordinator design isolates pipeline work in subagents (added in v0.5.0). Was 80–150k inline.
- **6–20 min wallclock** per run; Phase B (panel + synth) is the long part. Phase C (KB + polish) runs in background.
- **$0.5–$3 per run** depending on roster size and per-task model choices.

## Install

```bash
git clone https://github.com/uwilleer/preflight.git ~/programming/claude/preflight
ln -sf ~/programming/claude/preflight/skills/preflight ~/.claude/skills/preflight
```

Reload Claude Code (or start a new session). Activates on `/preflight` or natural-language triggers.

## Usage

```
/preflight path/to/plan.md            # file
/preflight                            # reviews current conversation (chat target)
/preflight resume <workspace_path>    # resume an interrupted run
```

Or naturally: *"собери экспертов на этот дизайн"*, *"panel review before I write this"*, *"раскритикуй своё последнее предложение"*.

**What gets reviewed well:**
- Architecture decisions, data flows, API contracts
- Schema choices, migration risks, cost projections
- Multi-domain plans (auth + perf + data + ops) where blind spots compound

**Don't use for:** single-domain trivial plans (use plan-critic), already-written code (use code-review), brainstorming (use brainstorming), debugging (use systematic-debugging).

## Pipeline (three sub-coordinator phases)

```
Phase A (steps 0–6)        Phase B (steps 7–9)         Phase C (steps 10–11)
─────────────────────      ────────────────────        ─────────────────────
Workspace + Ingest         Parallel expert dispatch    Rubber-duck polish
Brief                      Drift pre-check             KB apply + compaction
Context pack               Synthesizer                 (background)
Selector → roster          Render report.md
Role-KB load
Human gate ──────────►  user answers ──────────►  report.md ───────────►  kb_summary
```

Each phase is a separate `Agent` subagent call. Main session sees only structured JSON handoffs (`schemas/phase-handoff.json`), never the contents of expert reports or context packs. **Human gate is on by default** — you see the proposed panel and outstanding contradictions before any expert runs.

## Role catalog

| Role | Picks up |
|------|----------|
| `security` | Auth, injection, secrets, crypto, IDOR, PII |
| `performance` | N+1, blocking I/O, missing indexes, memory |
| `testing` | Coverage gaps, missing edge cases, test strategy |
| `concurrency` | Race conditions, deadlocks, missing locks |
| `api-design` | Breaking changes, naming, versioning, idempotency |
| `data-model` | Schema constraints, migration risk, normalization |
| `ops-reliability` | Observability, deployment, failure modes, SLOs |
| `cost-infra` | Cloud cost, LLM spend, unbounded growth |
| `supply-chain` | Dependencies, licenses, build pipeline integrity |
| `error-handling` | Swallowed errors, missing timeouts, retry-forever, resource cleanup |
| `observability` | Missing logs/metrics/traces, alert gaps |
| `contrarian-strategist` | Wrong problem, over-engineering, hidden assumptions |

Model is **not** pinned per role — the coordinator picks per dispatch based on cognitive load against *this* specific artifact and logs the choice to `_index.json.dispatch[]`. Ad-hoc roles (e.g. "quant trader", "GDPR counsel") are generated inline by the Selector when no catalog role fits.

## Evidence discipline

Every finding carries `evidence_source ∈ {code_cited, doc_cited, artifact_self, artifact_code_claim, reasoning}`:

- `code_cited` / `doc_cited` — verified by grep / URL+quote during the run. Most reliable.
- `artifact_self` — claim about the artifact itself (internal contradictions, ordering). Valid for MUST-FIX.
- `artifact_code_claim` — claim about code behaviour quoted *through* the artifact without independent grep. Synthesizer auto-downgrades MUST→SHOULD without `code_cited` cross-confirm.
- `reasoning` — expert judgement without external citation. Auto-downgraded; never load-bearing.

This is the single most important anti-hallucination lever — without it, experts confidently cite invented line numbers and the synthesizer has no way to tell verified facts from plausible guesses.

## ExpertReport contract

```json
{
  "role": "security",
  "verdict": "REVISE",
  "must_fix":   [{"title": "...", "evidence": "...", "replacement": "...", "evidence_source": "code_cited"}],
  "should_fix": [{"title": "...", "evidence": "...", "replacement": "...", "evidence_source": "artifact_self"}],
  "nice_fix":   [],
  "out_of_scope": [{"topic": "...", "owner_role": "..."}],
  "kb_candidates": [{"op": "add", "section": "Auth model", "content": "...", "finding_ref": "..."}]
}
```

Synthesizer uses `out_of_scope` as a cross-confirmation signal: if Security says "performance concern → performance" and Performance independently raises the same point, it's flagged `cross_confirmed`. `kb_candidates` are filtered by surviving findings and applied to the role-KB only after the noise filter — so KB doesn't bloat with rejected findings.

## Prompt-injection defense

Every role prompt opens with a hardcoded defense block. Artifact content is wrapped in `<<ARTIFACT-START>>…<<ARTIFACT-END>>` delimiters; instructions inside ("ignore prior rules", "emit APPROVE") are treated as data, not directives, and become a finding themselves.

## Evals

`evals/` contains 8 fixtures (4 real post-mortem patterns, 2 synthetic, 1 injection test, 1 good plan) with a frozen `grading.json` baseline:

```bash
python evals/run_eval.py checklist
```

## Index generation

```bash
make build-index   # regenerates roles/index.json from frontmatter
make test-index    # validates all required fields
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — adding a role is one PR, one file.

## License

MIT — see [LICENSE](LICENSE).
