# 2026-05-07 — Optimization analysis (session handoff)

Full reasoning behind the timing-instrumentation commit (`a5627f2`) and the deferred optimization roadmap. Captured here so the analysis survives the chat session and a future contributor (or the same author 3 months later) does not relitigate from scratch.

Companion documents:

- `docs/specs/2026-05-07-pyramidal-preflight-future-direction.md` — separate user-proposed idea (multi-layer cascading panels), why it's deferred independently of the three optimization PRs below.
- `CHANGELOG.md` `[Unreleased]` — short summary of what landed.
- `SKILL.md` "Timing instrumentation" section — runtime contract.

## Pipeline map (where the wall-clock goes today)

```
Phase A (1 spawn, internally sequential):
  init → ingest → brief.1 → context_decide → context_pack →
  brief.2 → selector(Agent inline) → role-KB merge → gate

Phase B (round-trip loop, 5 spawns worst-case):
  spawn1 → emit step 7 dispatch
    └─ main: run N experts ║ parallel
  spawn2 → emit step 7.5 dispatch (or skip → step 8 emit)
    └─ main: run N adversarial ║ parallel
  spawn3 → drift check (inline) → emit step 8 dispatch
    └─ main: run synthesizer (single)
  spawn4 → emit step 8.5 dispatch (or skip → step 9 inline)
    └─ main: run ≤12 verifiers ║ parallel
  spawn5 → render report (inline) → action: complete

Phase C (BG loop, 2-3 spawns):
  spawn1 → rubber-duck dispatch (or skip)
    └─ main: run rubber-duck (single)
  spawn2 → kb-apply (inline) + maybe compactor dispatch (parallel per role)
    └─ main: run compactors ║ parallel
  spawn3 → complete
```

Within each "fan-out wave" (steps 7, 7.5, 8.5, 11) parallelism already works correctly — single message with N `Agent` calls, parallel execution. The remaining latency lives in:

1. **Coordinator round-trips** — 5 sequential coordinator spawns in Phase B contribute ~25–50s of orchestration latency on top of the actual LLM work. This is intentional architectural cost: keeps main-session context at ~50k vs 80–150k inline. Cannot be reduced without one of (a) Anthropic delivering `Agent` to subagent contexts (out of skill's control), (b) collapsing back to inline (re-introduces context bloat the v0.7.0 split was created to fix).
2. **Drift pre-check** — runs synchronously at step 8.emit inside the coordinator. If `git rev-parse HEAD` shows the SHA moved during Phase B, ground_truth's `file_verifications` are re-grepped. 5–30s when triggered, 0 when stable.
3. **Phase C round-trips** — 2 sequential rubber-duck → kb-apply/compactor. BG, not user-visible, but burns cache.

## Three optimization PRs gated on data

The three PRs below were identified as the only points where additional parallelism / overlap helps **without** changing the result. Each is gated on empirical timing data because none of them has a guaranteed win — they save 0 to N seconds depending on real workload characteristics that the new instrumentation will reveal.

### PR #2 — Phase C single dispatch (collapse two round-trips to one)

**What:** Phase C currently emits rubber-duck dispatch, waits, resumes coordinator, applies KB inline, maybe emits compactor dispatch. Collapse so the coordinator emits **one** parallel-dispatch combining rubber-duck + per-role compactors, with kb-apply done inline by main session before the dispatch fans out.

**Why correct:** rubber-duck reads `report.md` + `synth_result.json`; compactor reads its KB file; kb-apply writes to `~/.claude/preflight-kb/<scope>/<role>.md`. Three non-overlapping file sets — no race, no data dependency between them. Today they run sequentially out of pipeline-design conservatism, not necessity.

**Estimated win:** 5–15s saved per Phase C run (BG, not user-visible); 1 fewer coordinator spawn → reduced cache burn.

**Files touched:** `meta-agents/sub-coordinator-phase-c.md` (collapse step-10 and step-11 emit logic into a single emit), `SKILL.md` Phase C section (update dispatch instructions). Schemas untouched. Tests: validate-handoff-examples passes; manual /preflight on a small fixture confirms Phase C completes in one resume round-trip.

**Risk:** low. BG-only, non-blocking, Phase C error mode is already non-blocking per existing contract.

### PR #3 — drift pre-check overlap with adversarial round

**What:** when main session emits the step-7.5 dispatch (N adversarial Agent calls in parallel), include in the **same multi-tool message** a Bash call running `git rev-parse HEAD`, and — only if the SHA differs from `ground_truth.git_sha` — a haiku subagent that re-runs `file_verifications` against the new HEAD, writing the refreshed `ground_truth.json` back to workspace. The coordinator on the post-7.5 resume reads the already-updated `ground_truth.json` instead of running drift check inline at step 8.emit.

**Why correct:** drift pre-check produces the same `ground_truth.json` either way. Moving its execution earlier — overlapped with adversarial — does not change the output, only the wall clock. Step 8 still gates on `ground_truth.json` existence; coordinator's reading is identical.

**Estimated win:** 1–30s situational. On stable branches with no rebases mid-run: ~0s (drift check trivial). On active branches where HEAD moves during a /preflight invocation: 5–30s.

**Files touched:** `SKILL.md` Phase B section (step-7.5 dispatch instructions gain a parallel side-task), `meta-agents/sub-coordinator-phase-b.md` step 8.emit (drift check becomes "trust ground_truth.json from main if main updated it; otherwise run inline as today").

**Risk:** medium. Needs careful contract: main writes `_index.json.drift_pre_check = {checked_at, sha_observed, refreshed: bool}` so coordinator knows whether to run inline drift or skip. Race between main's write and coordinator's read mediated by the round-trip resume (main writes before re-spawning coordinator). Fallback: coordinator can still run drift inline if main's marker is absent, so a partial implementation degrades gracefully.

### PR #4 — coordinator markdown trim + prompt-cache exploitation

**What:** each Phase B coordinator spawn loads the full ~500-line `sub-coordinator-phase-b.md` (~4k tokens) as its prompt prefix. 5 spawns × 4k = 20k tokens of static prefix per Phase B run. Two changes:

1. **Extract verbose anti-pattern blocks and rationale into supplementary files** the coordinator only reads when needed (e.g. `meta-agents/phase-b-anti-patterns.md`). Reduces hot-path prefix to ~2k tokens.
2. **Verify byte-identical prefix across all 5 spawns within a single Phase B run** — coordinator prompt is everything before the JSON inputs block; only `resume_token` varies, and that's in the inputs JSON, not the static prefix. If byte-identical and within Anthropic's prompt-cache TTL (5 min), spawns 2–5 hit the cache and pay ~10% of fresh tokens.

**Estimated win:** 10–25s per Phase B run (highly dependent on whether Anthropic prompt cache fires through subagent dispatch — empirically unverified before this PR).

**Files touched:** all three `meta-agents/sub-coordinator-phase-{a,b,c}.md` (extract verbose sections), new `meta-agents/phase-b-anti-patterns.md` etc. as targets, `SKILL.md` (instruct main to use byte-identical prefix; document cache behaviour).

**Risk:** medium-high. Largest blast radius (touches all coordinator files + SKILL.md). Requires prompt-cache verification through Claude Code's harness — if the harness wraps subagent dispatch in a way that defeats the cache, the win evaporates. Don't pursue without timing instrumentation showing coordinator-spawn overhead is actually significant on real runs.

## Eager-work analysis (user's framing during the session)

User raised the principle: while the critical path is blocked waiting for an LLM batch, main session should not idle — it should run independent work whose inputs are already known. Map of where this is and isn't applicable in preflight, decided during this session:

### Applicable (subset of the three PRs above)

- **Window during step 7 (experts running, ~10–30s):** main can run `git rev-parse HEAD` (1ms) and pre-warm static synthesizer-prompt prefix (microoptimization, ~1–2s). The drift check belongs to the post-step-7.5 / pre-step-8 boundary, not step-7's window — but moving it into step-7.5's window is exactly PR #3.
- **Window during step 7.5 (adversarial running, ~10–20s):** drift re-grep if SHA moved (PR #3); pre-parse `kb_candidates` from `expert_reports/*.json` into memory for step 8.resume (~1–2s saved coordinator-side). Bundle the latter into PR #3.
- **Window during step 10 (rubber-duck running, BG):** kb-apply inline + compactor dispatch (PR #2).

### Not applicable (data-dependency blocks it)

- **Window during step 8 (synth running):** verifier targets are output of synth — cannot pre-build. Render skeleton: synth's job. KB-apply needs `surviving_titles` from synth.
- **Window during step 8.5 (verifiers running):** kb-apply COULD run (synth_result available), but step 8.5 mutates synth_result titles (prepending downgrade prefixes). Running kb-apply against pre-8.5 titles changes `dropped_as_noise` count vs sequential variant — affects results. **Rejected** on the "ни капли не повлияет" constraint.
- **Speculative branching** (run synth on N adversarial-output guesses, pick winner): violates the no-result-change constraint and burns cost. Rejected.

### Out of scope permanently

- Speculative work whose inputs require seeing prior LLM output. Pipeline data-dependencies are real, not architectural laziness.
- Anything that consumes more cost for marginal latency improvement when the user's stated rule is "don't optimize without measuring."

## Why timing instrumentation came first

The three PRs above each have a plausible-sounding win range (5–15s, 1–30s, 10–25s). Without empirical numbers from real /preflight runs, choosing among them — or deciding whether to pursue any — is intuition gambling. Specifically:

- PR #2 win is BG, non-user-facing. Worth doing only if Phase C latency matters in some measured workflow context (e.g. user runs back-to-back /preflight invocations and the second waits on the first's BG Phase C).
- PR #3 win is situational on HEAD movement during runs. If user typically /preflight's stable artefacts on stable branches, win is ~0 and the PR is dead weight.
- PR #4 win depends on Anthropic prompt-cache behaviour through Claude Code's subagent dispatch, which is empirically unverified. If cache doesn't fire across subagent boundaries, PR #4 saves nothing.

`coordinator_spawns[]` and `dispatch[]` in `_index.json` produce the data needed to filter PRs into "real" and "imaginary" wins. Specifically:

- Per-spawn entry latency (`emit_at - started_at`) tells us coordinator overhead per spawn. If small (<2s), PR #4 likely a non-event.
- Per-step dispatch latency (`max(completed_at) - min(started_at)` over all `dispatch[]` entries with the same `step`) tells us LLM wall-clock per step. Compares against coordinator overhead to compute the orchestration tax.
- `attempt > 1` entries quantify retry rate, which feeds back into "how robust is the pipeline" — orthogonal to optimization but useful.
- Phase C `coordinator_spawns[]` entries tell us if Phase C is a noticeable wall-clock contributor at all, gating PR #2.

## Trigger for revisiting

Once `~/programming/claude/preflight/.preflight/runs/` contains 3+ run directories whose `_index.json` carries `coordinator_spawns[]` (post-`a5627f2` runs), aggregate the timing data:

1. Compute per-phase total latency = max(`emit_at` across all spawns of that phase) − min(`started_at` across all spawns of that phase).
2. Compute per-step dispatch latency.
3. Compute coordinator overhead = (sum of spawn durations) − (sum of step dispatch durations the spawns triggered).
4. Decide which of PR #2 / #3 / #4 has a real win >5s on average; abandon those that don't.

This is when the pyramidal-preflight `depth=` parameter becomes possible to design with real cost predictions, per the companion future-direction doc.

## Out of scope for this analysis

- Code-quality / style / formatting reviews via panels — formatter / linter / typechecker territory. See `docs/specs/2026-05-07-pyramidal-preflight-future-direction.md` "Out of scope, permanently."
- Mandatory pyramidal mode. Defaults stay opt-in; user retains budget control.
- Architecture changes that lift the round-trip loop (Anthropic-harness-level concern, not skill-level).