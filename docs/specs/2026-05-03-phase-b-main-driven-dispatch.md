# Phase B: main-driven `Agent` dispatch

> **Status:** Draft — design intent only, no implementation yet. Reviewer should challenge architecture choice (V2 over V1/V3), the handoff shape, and the resumability story before any code is written.
> **Successor to:** v0.6.5 (revert of dedicated subagent type). Targets v0.7.0.

## Problem

Phase B's core work — parallel expert dispatch (step 7), adversarial round (7.5), synthesizer call (8), verification mini-round (8.5) — requires the `Agent` meta-tool. The pipeline was designed (v0.5.0+) so a sub-coordinator subagent issues these `Agent` calls, returning only a small handoff JSON to the main session. This kept main-session context at ≈25k per `/preflight` regardless of artifact size or panel size.

**The architecture's core assumption — that a subagent can issue nested `Agent` calls — is empirically false in the current CC build.** Three sequential attempts at fixing this through frontmatter changes (PR #7 explicit `tools: [Agent, ...]`, PR #15 omitted `tools:`, then PR #17 revert to `general-purpose`) all observed the same failure mode: the spawned subagent receives a baseline toolset (`Bash, Edit, Read, ScheduleWakeup, Skill, ToolSearch, Write`) that does **not** include `Agent`, and `ToolSearch select:Agent` returns `"No matching deferred tools found"`. The behaviour holds for every non-`general-purpose` subagent type and — the new data point from 2026-05-03 — also for `general-purpose` itself.

Only the **main session** has `Agent` in its active toolset. Any spawned subagent loses it.

## Evidence

Three runs across two days, three different frontmatter configurations, identical symptom:

| Run | Date | Frontmatter shape | Default toolset of spawned coordinator | `ToolSearch select:Agent` |
|---|---|---|---|---|
| `proxy-d8032268/20260503-0935-architecture-v2/` | 2026-05-03 09:35 | `tools: [Agent, Read, Bash, Write, Glob, Grep, ToolSearch, WebFetch, WebSearch]` (PR #7) | (not logged — coordinator wrote `phase-b-error.json` at step 0) | "No matching deferred tools found" |
| `vitok-1b4a9653/20260503-1407-session2-signing/` | 2026-05-03 14:07 | same as above (PR #7) | same | same |
| post-PR-#15 fresh CC session | 2026-05-03 ~16:00 | no `tools:` field (PR #15) | `Bash, Edit, Read, ScheduleWakeup, Skill, ToolSearch, Write` | same |
| post-PR-#17 fresh CC session, `subagent_type: general-purpose` | 2026-05-03 ~17:00 | (no agent file at all) | `Bash, Edit, Read, Skill, ToolSearch, Write, ScheduleWakeup` | same |

Phase A's selector (which also wants `Agent` to spawn the selector subagent) survives because it has an inline-fallback path written into `phase-a.md`: when `Agent` is unavailable, the coordinator runs the selector logic directly using `selector.md`'s rubric, recording `_selector_meta.executed: "inline (Agent tool unavailable...)"` in `roster.json`. Phase B has no analogous fallback because **N parallel expert dispatches cannot be done inline** — that defeats the point of the panel.

## Options

**V1 — Inline in main session.** SKILL.md (the orchestrator) does every `Agent` call directly. Phase B coordinator subagent goes away entirely; steps 7→9 become inline procedures in SKILL.md.
- ✅ Simple. No new handoff shapes. Fewest moving parts.
- ❌ Re-bloats main context — defeats v0.5.0's primary win. Heavy reads (role prompts, role-KB, context_pack slices, expert reports, synth result) all land in main.
- ❌ Long artifacts may push main past CC's effective deep-context budget.

**V2 — Round-trip for `Agent` calls only.** Phase B coordinator subagent stays. Logic — skip conditions, dispatch-set construction, dedup, summary writes, render — runs in the coordinator. Whenever an `Agent` call is needed, the coordinator returns to main with a `dispatch` handoff: "here is a list of N prompts, please execute and write results to these paths, then re-spawn me." Main does the `Agent` calls, writes results to the workspace, re-spawns the coordinator, which reads its state from disk and continues.
- ✅ Preserves v0.5.0's context discipline. Heavy artefacts stay in coordinator subagent. Main only carries small handoff JSONs and the dispatched prompts (which it does not need to re-read after dispatching).
- ✅ Resumability becomes natural — the coordinator already reads workspace state on each spawn; the round-trip pattern is just "more spawns, smaller deltas each."
- ❌ More round-trips per Phase B run (up to 4: step 7, 7.5, 8, 8.5).
- ❌ New handoff shape; small schema migration.
- ❌ Coordinator re-reads `_index.json` + `brief.md` etc. on every spawn — duplicated I/O cost.

**V3 — Status quo + formalised manual recovery.** Keep the broken architecture; document that main session does inline recovery on every Phase B failure as the official path. The pre-flight check still fires; main session does what `phase-b-error.json.trace` already recommends.
- ✅ Zero code change.
- ❌ Skill is broken in the eyes of every non-maintainer. Recovery requires the user to know what to type next; for non-Kirill installations this means "skill silently doesn't work."
- ❌ The "recovery" is ad-hoc; no test coverage; no consistent handoff JSON for tooling.

**Decision: V2.** Quality bar matters more than implementation cost (user direction: "Мы не торопимся. главное - качество"). V1's main-context regression undoes a design decision that was carefully justified across two prior releases. V3 leaves the skill effectively broken outside the maintainer's hands.

## Detailed design — V2

### Handoff schema extension

`phase_b_output` becomes a **discriminated union** keyed by `action`:

```json
{
  "action": "complete" | "dispatch" | "error",
  "workspace_path": "/abs/path",
  "last_completed_step": 7
}
```

**`action: "complete"`** — terminal success. Carries the existing v0.6.x fields (`report_path`, `report`, `report_too_long`, `skipped_experts`, `drift_refreshed`). Main session emits the report and spawns Phase C.

**`action: "error"`** — terminal failure. Carries `error_path` (existing). Main session reads, prints, stops — no Phase C.

**`action: "dispatch"`** — main session must execute a batch of `Agent` calls and re-spawn the coordinator. New shape:

```json
{
  "action": "dispatch",
  "workspace_path": "/abs/path",
  "last_completed_step": 7,
  "dispatch": {
    "step": "7.5",
    "step_label": "adversarial-round",
    "parallelism": "parallel",
    "requests": [
      {
        "id": "security",
        "subagent_type": "general-purpose",
        "model_hint": "sonnet",
        "description": "Preflight adversarial pass: security",
        "prompt": "<full prompt, ready to send>",
        "save_to": "/abs/path/expert_reports_post_adversarial/security.json",
        "schema_ref": "schemas/expert-report.json",
        "on_failure": "mark_skipped"
      }
    ],
    "resume_token": "post-step-7.5"
  }
}
```

Field semantics:
- **`step` / `step_label`** — informational, for logging and telemetry.
- **`parallelism`** — `"parallel"` (single-message multi-Agent dispatch, expected case) or `"sequential"` (rare; e.g. synthesizer waits for verifier output).
- **`requests[].id`** — stable identifier (role name, claim id, etc.) used by the coordinator on resume to map files back to logical units.
- **`requests[].prompt`** — the **complete** prompt body. Coordinator has already done all assembly (role prompt + claim-citation discipline + role-KB + context_pack slice + delimited artifact). Main is a dumb executor.
- **`requests[].save_to`** — absolute path. Main writes the `Agent` call's response there verbatim.
- **`requests[].on_failure`** — `"mark_skipped"` (record in `skipped_experts`, continue) or `"abort"` (re-spawn coordinator with the failure recorded in workspace; coordinator decides what to do).
- **`resume_token`** — opaque string the main passes back to the coordinator. The coordinator uses it (alongside `_index.json.last_completed_step` and the existence of files in `save_to` paths) to decide what to do next.

The schema for the existing fields stays the same — `action: "complete"` is wire-compatible with v0.6.x `phase_b_output`, only the union wrapping is new. Old runs and old workspaces remain readable.

### Coordinator state machine

The coordinator is now invoked **multiple times per Phase B run**, not once. Each invocation:

1. Read `_index.json`, `brief.md`, `ground_truth.json`, `roster.json`, `gate_answers.json`. (Same as today.)
2. Determine the **next pending step** by inspecting workspace state:
   - No `expert_reports/*.json` → next is step 7.
   - `expert_reports/*.json` present, no `adversarial_round.json` → evaluate skip condition; either jump to step 8 (skip) or emit step 7.5 dispatch.
   - `adversarial_round.json` present, no `synth_result.json` → emit step 8 dispatch (synthesizer).
   - `synth_result.json` present, no `verification_round.json` → evaluate skip condition; either jump to step 9 (skip) or emit step 8.5 dispatch.
   - All present → render step 9 inline, return `action: "complete"`.
3. If the next step requires `Agent`: build the `dispatch` payload, write any prep files (e.g. expert prompts can be persisted to `dispatch_plans/step-7.json` for audit), return `action: "dispatch"`.
4. If the next step is pure rendering (step 9): execute inline, write `report.md`, return `action: "complete"`.

The coordinator never calls `Agent` itself. The pre-flight `Agent` check from 0.6.1 stays only as documentation of the constraint — under V2 it is no longer load-bearing.

### Main session orchestration loop

SKILL.md's Phase B handler becomes a simple loop:

```
result = spawn_coordinator(workspace_path, gate_answers_path, user_language, resume_token=null)
loop:
  if result.action == "complete": emit_report(result); spawn_phase_c(); break
  if result.action == "error":    surface_error(result); break
  if result.action == "dispatch":
    if result.dispatch.parallelism == "parallel":
      # single message with N Agent tool calls
      responses = [Agent(**req_to_kwargs(r)) for r in result.dispatch.requests]
    else:
      # sequential: one Agent call at a time
      responses = []
      for r in result.dispatch.requests:
        responses.append(Agent(**req_to_kwargs(r)))
    for r, resp in zip(result.dispatch.requests, responses):
      handle_response(r, resp)  # write to r.save_to or record skipped per r.on_failure
    result = spawn_coordinator(workspace_path, ..., resume_token=result.dispatch.resume_token)
```

Round-trip count per Phase B run: **at most 5** coordinator spawns (initial + 4 dispatch round-trips: 7, 7.5, 8, 8.5). Common case is 3–4 (verification or adversarial may skip).

### Resumability across CC sessions

The state machine reads workspace files to decide the next pending step, so cross-session resume is automatic. `/preflight resume <workspace_path>` works the same way as today: spawn coordinator with `resume_token=null`, it inspects files, emits the next dispatch (or `complete` if everything is on disk).

A user can kill CC mid-Phase-B-dispatch (e.g. between main's `Agent` calls and the next coordinator re-spawn). On resume, the partial files in `expert_reports/` will be detected — the coordinator either re-emits the missing dispatches (re-running the failed/missing roles) or proceeds to the next step depending on what's complete. **This is identical to the existing v0.6.x resume semantics**; the round-trip pattern doesn't change it.

## Phase C — analogous, smaller scope

Phase C has two `Agent` calls: rubber-duck (step 10, conditional) and KB compactor (step 11, conditional). Both single-shot, neither parallel. The same V2 pattern applies but degenerate:

- Phase C coordinator reads workspace state, decides if rubber-duck is needed (skip on `target_type ∈ {chat, inline}` or artifact < 4k). If skipped, jumps to step 11.
- For each needed Agent call, returns one `dispatch` request, parallelism = `"sequential"` (it's only one).
- Main executes, writes result, re-spawns.
- Step 11 has KB-write logic that is pure file I/O — runs inline in coordinator after the compactor result is on disk. Returns `action: "complete"` with `kb_summary`.

Worst case Phase C: 3 coordinator spawns (initial → rubber-duck dispatch → compactor dispatch → final). Phase C is `run_in_background: true`, so this is invisible to the user UX.

## Schema changes

Additive only — old `phase_b_output` and `phase_c_output` remain valid:

- `phase_b_output.action`: new field, enum `["complete", "dispatch", "error"]`. Default semantics for absent field = `"complete"` (backward-compat for any tool that consumes the schema).
- `phase_b_output.dispatch`: new optional object, present iff `action == "dispatch"`. Sub-shape defined above.
- `phase_b_input.resume_token`: new optional string field, present on coordinator re-spawns within a single Phase B run.
- `phase_c_output.action` + `phase_c_output.dispatch`: identical pattern.
- `phase_c_input.resume_token`: same.

No changes to `expert-report.json` or `synth_result` — those are workspace-internal schemas, untouched by the round-trip pattern.

## Implementation plan (high level — full task list separate)

1. **Schema first.** Extend `phase-handoff.json` with the union shapes. Add JSON-schema validation tests against fixtures of all three `action` variants. Land before any prompt changes so the contract is locked.
2. **Phase B coordinator rewrite.** Each numbered step in `sub-coordinator-phase-b.md` becomes a state-machine branch. Pre-flight `Agent` check turns into a no-op (kept for documentation only — coordinator never calls Agent under V2).
3. **SKILL.md Phase B handler.** Replace single-spawn pattern with the loop. Document the loop's invariants in the existing "Anti-patterns" section.
4. **Phase C coordinator rewrite.** Same pattern, single-shot dispatches.
5. **Evals migration.** Existing fixtures replay through the new architecture; the loop should be transparent at the workspace/output level. Update `evals-grading-v3` only if behaviour changes — this PR aims for behaviour-equivalence.
6. **CHANGELOG entry as 0.7.0.** This is the first minor bump that changes the orchestration contract; existing code consuming `phase_b_output` may need an `action` switch.

## Open questions for review

1. **Should we ship V2 as 0.7.0 or 1.0.0?** It changes the SKILL.md ↔ coordinator contract — wire-compatible for the `complete` path, new for `dispatch`. Argument for 1.0.0: the architecture is now stable against the empirical harness reality, which feels like a good moment to declare the API fixed. Argument for 0.7.0: we're still iterating; 1.0.0 implies we wouldn't break the `dispatch` shape going forward.

2. **`on_failure: "mark_skipped"` policy granularity.** Today's behaviour is binary per role (skip after two consecutive malformed JSONs). The new shape lets us be smarter — e.g. allow main to retry once with a terser prompt before declaring `skipped`. Worth implementing now or YAGNI?

3. **`dispatch_plans/step-N.json` audit files.** Should the coordinator persist the dispatch plan it sent before main executes? Pro: clean audit trail, easy debugging of "what prompt did the security expert see?". Con: doubles workspace write traffic. Compromise: write only on `_index.json.preflight_audit_dispatch == true` opt-in.

4. **Phase C and `run_in_background`.** The current Phase C handoff is async — main gets a notification when the single coordinator spawn finishes. Under V2 it's a loop with multiple spawns. Does CC's `run_in_background` notification model work for a loop, or do we need to keep Phase C to a single foreground spawn (and accept the user UX cost of waiting on KB compaction)? Needs harness check before code.

5. **Inline-fallback for selector after Phase A revert.** Phase A still uses a coordinator subagent for steps 0–6, and its selector path uses inline-fallback when `Agent` is missing. Under the V2 lens, should Phase A also adopt the dispatch-round-trip pattern for consistency? The cost is one extra round-trip on every run, even when selector is the only Agent call. Probably YAGNI — selector's inline fallback works and is simpler.

## Migration

- Workspaces from v0.6.x remain readable. Coordinator's "what's the next pending step" logic only inspects file existence — pre-V2 workspaces with full state on disk produce `action: "complete"` immediately on first spawn (rendering from existing `synth_result.json`).
- `/preflight resume <old workspace>` works unchanged.
- Users on 0.6.x do not need any local action besides upgrading the skill checkout. No symlinks to add or remove.

## Anti-goals

- We are not redesigning the pipeline. The 12-step model stays. The expert prompts stay. The workspace layout stays. V2 only changes **who issues the `Agent` calls** (main session vs coordinator) — everything else is preserved.
- We are not adding parallelism beyond what already exists in step 7 / 7.5 / 8.5. Sequential calls (synthesizer at step 8, rubber-duck at step 10) stay sequential.
- We are not introducing a queue or persistent dispatch broker. Round-trips are synchronous within a single Phase B run; the only persistence is workspace files (already there).
