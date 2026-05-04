# Preflight architecture overview

Single-page entry point for new contributors. Read this before diving into
`SKILL.md` or any of the meta-agent prompts. For sample output and install,
see [README.md](../README.md). For the full design history, see
[docs/specs/2026-04-20-preflight-design.md](specs/2026-04-20-preflight-design.md).

## Three actors

| Actor | Lives in | Job | Token cost | Sees |
|---|---|---|---|---|
| **Main session** | Your `Claude Code` window | Spawns coordinators, executes `Agent` calls the coordinators ask for, relays handoffs back to the user. **Dumb executor — never thinks about the artifact.** | Smallest (~50k per run) | Only structured JSON handoffs |
| **Sub-coordinators** | `meta-agents/sub-coordinator-phase-{a,b,c}.md` — spawned subagents | State machines over workspace files. Decide the next pending step, build dispatch payloads, never call `Agent` themselves under v0.7.0. | Medium | Workspace files |
| **Experts + helpers** | `roles/*.md` (panel) + `meta-agents/{selector, synthesizer, verifier, adversarial, rubber-duck}.md` | Actual work: review the artifact, dedup findings, verify claims, polish output. Each gets a fresh subagent context. | Largest (varies by panel size) | Their own slice of the workspace + the artifact |

The split exists because (a) one agent can't fit the whole pipeline in
context, and (b) empirically the `Agent` tool is not delivered to spawned
subagents in current CC builds — so the coordinator can't dispatch work
itself, only main can. Coordinators decide *what* to dispatch; main *executes* the dispatch.

## Three phases, dispatch-loop state machines (v0.7.0)

```
Phase A (steps 0–6)        Phase B (steps 7–9)         Phase C (steps 10–11)
─────────────────────      ─────────────────────       ─────────────────────
Workspace + Ingest         Parallel expert dispatch    Rubber-duck polish
Brief                      Adversarial round (7.5)     KB apply (inline)
Context pack               Drift pre-check + Synth     KB compaction
Selector → roster          Verifier mini-round (8.5)
Role-KB load               Render report.md
Human gate ──────────►  user answers ──────────►  report.md ───────────►  kb_summary
```

Phase A is a single coordinator spawn (its only `Agent`-needing step,
the selector, has an inline-fallback when `Agent` isn't available).

Phase B and Phase C are **dispatch loops**. Each coordinator spawn returns
one of three handoff shapes:

- **`action: "complete"`** — terminal success, hand `report` (or `kb_summary`)
  back to main.
- **`action: "dispatch"`** — main, please execute these N `Agent` calls
  (`parallelism: parallel | sequential`), write each result to the
  specified `save_to` path, then re-spawn me with `resume_token`.
- **`action: "error"`** — terminal failure, here's the error file path.

Phase B worst case: **5 coordinator spawns** (initial + 4 dispatch round-trips
for steps 7, 7.5, 8, 8.5). Phase C worst case: **3 spawns** (initial +
rubber-duck + KB compactor). Phase C runs every spawn with `run_in_background:
true` — non-blocking, the user already has Phase B's report.

## Workspace layout

Every run gets its own workspace under `<scope>/.preflight/runs/<timestamp>-<slug>/`:

```
_index.json                       — run state machine: last_completed_step, dispatch[], drift_refreshed, …
brief.md                          — synthesized artifact summary (Phase A)
ground_truth.json                 — file_verifications + already_done + load_bearing_facts (Phase A)
context_pack.json                 — conventions/architecture/api_surface/data_flows/storage/external_deps slices
gate.md                           — questions for the user (only if Phase A surfaces blockers)
gate_answers.json                 — user's answers, written by main session
expert_reports/<role>.json        — first-pass ExpertReports (Phase B step 7)
expert_reports_post_adversarial/  — second-pass reports (Phase B step 7.5, optional)
synth_result.json                 — synthesizer output (Phase B step 8)
verifier_results/<id>.json        — per-claim verification (Phase B step 8.5)
verification_round.json           — verifier roll-up
report.md                         — rendered report (Phase B step 9)
report.polished.md                — rubber-duck output (Phase C step 10)
kb_applied.json                   — per-role KB write summary (Phase C step 11)
kb_compacted/<role>.md            — staging files before compactor overwrites personal KB
phase-{a,b,c}-error.json          — only on terminal error
```

The coordinator's "what's the next pending step" logic only inspects file
existence — that's why resume works (`/preflight resume <workspace_path>`).

## Handoff contract

`schemas/phase-handoff.json` is the wire shape between main and coordinators.
Phase B/C outputs are discriminated unions keyed by `action`. Canonical
positive and negative shapes live in `schemas/_examples/phase_{b,c}_*.json`
and are validated by `make test-handoff`.

`schemas/expert-report.json` is the contract every expert role must obey.
`schemas/verifier-result.json` is the verifier's output (added in v0.7.1
with the `ground_truth_match` field to support the rescue-promotion path).

## Model selection policy

Per-task model choice lives in `request.model_hint` (set by the coordinator
at dispatch construction, passed by main to `Agent`'s `model` parameter).

- **Sonnet floor** for everything that requires judgment: coordinators,
  selector, every expert role, synthesizer, verifier, adversarial round,
  rubber-duck.
- **Haiku** is reserved for **mechanical text transforms**. Currently the
  only such task is the **KB compactor** (Phase C step 11) — it dedups
  bullets and reformats by a fixed schema, no severity/correctness calls.
- **Opus** for adversarial-reasoning roles (security, contrarian-strategist)
  and for synthesizer when the panel is large or in conflict.

Roles' frontmatter `model` is an advisory hint; the coordinator makes the
real per-dispatch call based on this artifact's load and logs the choice
to `_index.json.dispatch[].model`. The selector deliberately strips
role-level `model` (see `meta-agents/selector.md`).

## Where to find what (contributor map)

| You want to… | Look at |
|---|---|
| Add a new expert role | `CONTRIBUTING.md`, `roles/*.md`, `roles/index.json` (regen via `make build-index`) |
| Add a signal-group augmenter | `roles/signals/README.md`, `roles/signals/*.yaml` |
| Change the panel-selection logic | `meta-agents/selector.md` |
| Change the dispatch loop / state machine | `meta-agents/sub-coordinator-phase-{a,b,c}.md` |
| Change synthesis (dedup, severity, decision cards) | `meta-agents/synthesizer.md` |
| Change verifier rules | `meta-agents/verifier.md`, `schemas/verifier-result.json` |
| Change adversarial-round prompt | `meta-agents/adversarial.md` |
| Change rubber-duck polishing rules | `meta-agents/rubber-duck.md` |
| Change main-session orchestration | `SKILL.md` |
| Add an eval fixture | `evals/fixtures/<slug>/plan.md`, then update `evals/grading.json` |

## Design rationale (short)

**Why state-machine coordinators?** v0.6.x had coordinators that called
`Agent` themselves. The empirical CC limitation (`Agent` not delivered to
spawned subagents) made that unworkable. v0.7.0 inverts the pattern:
coordinators decide, main executes. Round-trip overhead is real (~25k
extra context vs. v0.6.x), but still well below the ~100k cost of running
the whole pipeline inline.

**Why workspace files instead of in-memory state?** Resumability. A
`/preflight` run can be interrupted at any step and resumed by re-spawning
the coordinator with `resume_from: <workspace_path>`. The state machine's
"next step" logic is pure file-existence inspection.

**Why separate verifier mini-round (8.5)?** Anti-hallucination. The
synthesizer auto-downgrades any `must_fix` whose `evidence_source` is
weaker than `code_cited` and lacks cross-confirmation. The verifier mini-
round catches downgrades the synthesizer was wrong to apply (when
`ground_truth` actually backs the claim — added in v0.7.1) and confirms
downgrades it was right to apply.

**Why background Phase C?** Polish + KB compaction are non-blocking
side-quests. The user already has Phase B's report; they should not wait
for the rubber-duck to ship.
