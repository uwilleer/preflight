# Phase B main-driven dispatch — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task ends with a verification step that MUST pass before moving on.
>
> **Design reference:** `docs/specs/2026-05-03-phase-b-main-driven-dispatch.md` (merged via #18). Read that first — this plan implements it.

**Goal:** Ship v0.7.0 — Phase B coordinator stops calling `Agent` directly. Instead it returns `dispatch` handoffs to the main session, which executes the `Agent` calls and re-spawns the coordinator. Same applies to Phase C iff Task 0 confirms harness compatibility.

**Architecture (locked):** V2 from the design spec. Discriminated-union handoff (`action: complete | dispatch | error`). Coordinator never calls `Agent`. Workspace files are the state checkpoints — coordinator decides next step by inspecting which files exist.

**Tech stack:** Markdown prompt files (meta-agents), JSON-schema (handoffs). No new languages, no Python deps. Behaviour-equivalent to v0.6.5 at the workspace/output level — eval grading should not need `evals-grading-v3` → `v4` bump unless Task 7 surfaces a divergence.

**Defaults baked in (in absence of explicit answers to design spec's open questions):**

| Open question | Decision |
|---|---|
| Versioning | **0.7.0** (still iterating; no 1.0.0 commitment) |
| `on_failure` policy | **Binary** (`mark_skipped` / `abort`); no smart retry — match 0.6.x semantics |
| Audit files (`dispatch_plans/`) | **Opt-in only**, gated by `_index.json.preflight_audit_dispatch == true`; default off; not implemented in v0.7.0 (YAGNI until someone asks) |
| Phase C + `run_in_background` | **Decided by Task 0 probe** (foreground fallback if loop incompatible) |
| Phase A consistency | **No change** — selector inline-fallback stays |

---

## File structure

**Created:**
- `skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md` — short artefact from Task 0 documenting the harness probe result. Becomes the load-bearing reference for the Phase C path choice.

**Modified:**
- `skills/preflight/schemas/phase-handoff.json` — `phase_b_output` and `phase_c_output` extended with `action` discriminator + `dispatch` sub-shape; `phase_b_input` and `phase_c_input` gain optional `resume_token`.
- `skills/preflight/meta-agents/sub-coordinator-phase-b.md` — full rewrite of the steps section: state-machine on workspace files, no `Agent` calls, dispatch handoffs.
- `skills/preflight/meta-agents/sub-coordinator-phase-c.md` — same pattern, smaller scope (rubber-duck + KB compactor).
- `skills/preflight/SKILL.md` — Phase B handler becomes a loop; Phase C handler gated on Task 0 result.
- `CHANGELOG.md` — 0.7.0 entry.
- `docs/specs/2026-04-20-preflight-design.md` §7.5 / §8 / §10–11 — mention the new round-trip pattern; section diagrams updated.

**Deleted:** none. Old workspaces remain readable; `agents/` directory was already removed in 0.6.5.

---

## Task 0 — Probe: does main-session loop survive `run_in_background`?

**Files:** Create `skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md`.

The whole Phase C question hinges on one harness behaviour: if the main session spawns `Agent(run_in_background: true, …)` and the spawned subagent returns a `dispatch` handoff, can the main session execute the dispatched calls and re-spawn the coordinator (also background) without losing the notification chain? Or does background mode only support a single fire-and-forget spawn?

We do not know this from documentation. We probe.

- [ ] **Step 1 — Construct minimal probe.**

  In a scratch CC session (not the preflight repo), create:

  ```
  Agent(
    subagent_type: general-purpose,
    description: "BG loop probe step 1",
    run_in_background: true,
    prompt: "Return ONLY this JSON: {\"action\": \"dispatch\", \"resume_token\": \"step-2\"}"
  )
  ```

  Wait for the notification. Read the result.

- [ ] **Step 2 — Re-spawn from main on the notification, also background.**

  ```
  Agent(
    subagent_type: general-purpose,
    description: "BG loop probe step 2",
    run_in_background: true,
    prompt: "Return ONLY: {\"action\": \"complete\"}"
  )
  ```

  Wait. Did the second notification arrive? Did the main session correctly chain the two?

- [ ] **Step 3 — Document outcome in the notes file.**

  Write `skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md` with:
  - exact probe transcript (anonymised if needed)
  - one-line verdict: `BG_LOOP_OK: true | false`
  - implication for Phase C: if `true` → loop pattern; if `false` → foreground for the loop, sacrifice the user-invisible UX gain

- [ ] **Step 4 — Commit the notes file alone.**

  ```bash
  git add skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md
  git commit -m "task 0: phase-c bg loop probe result (BG_LOOP_OK=<bool>)"
  ```

  Verification: `cat skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md | grep BG_LOOP_OK` returns one line.

**Stop here if:** the probe is inconclusive. Surface to the maintainer; do not guess. Phase B (Tasks 1–3) does not depend on this result and can proceed in parallel.

---

## Task 1 — Schema extension (additive)

**Files:** `skills/preflight/schemas/phase-handoff.json`

The new shape must be wire-compatible for the `complete` path so any existing tooling consuming `phase_b_output` keeps working.

- [ ] **Step 1 — Extend `phase_b_output` to the discriminated union.**

  Replace the current `phase_b_output` definition with:

  ```json
  "phase_b_output": {
    "type": "object",
    "required": ["workspace_path", "last_completed_step", "action"],
    "properties": {
      "workspace_path": { "type": "string" },
      "last_completed_step": { "type": "integer", "minimum": 7, "maximum": 9 },
      "action": { "type": "string", "enum": ["complete", "dispatch", "error"] },

      "report_path": { "type": "string" },
      "report":      { "type": "string", "maxLength": 15000 },
      "report_too_long": { "type": "boolean" },
      "skipped_experts": { "type": "array", "items": { "type": "string" } },
      "drift_refreshed": { "type": "boolean" },

      "dispatch": { "$ref": "#/definitions/phase_b_dispatch" },

      "error_path": { "type": ["string", "null"] }
    },
    "allOf": [
      { "if": { "properties": { "action": { "const": "complete" } } },
        "then": { "required": ["report_path"] } },
      { "if": { "properties": { "action": { "const": "dispatch" } } },
        "then": { "required": ["dispatch"] } },
      { "if": { "properties": { "action": { "const": "error" } } },
        "then": { "required": ["error_path"] } }
    ]
  }
  ```

  Add a new `phase_b_dispatch` definition under `definitions`:

  ```json
  "phase_b_dispatch": {
    "type": "object",
    "required": ["step", "step_label", "parallelism", "requests", "resume_token"],
    "properties": {
      "step":          { "type": "string", "enum": ["7", "7.5", "8", "8.5"] },
      "step_label":    { "type": "string" },
      "parallelism":   { "type": "string", "enum": ["parallel", "sequential"] },
      "requests": {
        "type": "array",
        "minItems": 1,
        "items": {
          "type": "object",
          "required": ["id", "subagent_type", "description", "prompt", "save_to", "on_failure"],
          "properties": {
            "id":            { "type": "string" },
            "subagent_type": { "type": "string" },
            "model_hint":    { "type": "string" },
            "description":   { "type": "string" },
            "prompt":        { "type": "string" },
            "save_to":       { "type": "string" },
            "schema_ref":    { "type": "string" },
            "on_failure":    { "type": "string", "enum": ["mark_skipped", "abort"] }
          }
        }
      },
      "resume_token": { "type": "string" }
    }
  }
  ```

- [ ] **Step 2 — Add `resume_token` to `phase_b_input`.**

  In `phase_b_input.properties`, add:

  ```json
  "resume_token": {
    "type": ["string", "null"],
    "description": "Set on coordinator re-spawns within a single Phase B run. The coordinator uses it (alongside _index.json.last_completed_step and which workspace files exist) to decide what to do next. null on first spawn."
  }
  ```

  Do NOT add to `required[]` — first spawn omits it.

- [ ] **Step 3 — Mirror Phase C if Task 0 returned `BG_LOOP_OK: true`.**

  If the probe succeeded, repeat Step 1 + Step 2 for `phase_c_output` and `phase_c_input` (analogous fields). Cap `phase_c_dispatch.step` enum at `["10", "11"]`.

  If the probe failed, leave Phase C schemas unchanged for v0.7.0 — Phase C stays single-spawn foreground (decided in Task 4).

- [ ] **Step 4 — Validate sample handoffs against the new schema.**

  Create `skills/preflight/schemas/_examples/phase_b_complete.json`, `phase_b_dispatch.json`, `phase_b_error.json` (one fixture per `action` value). Run:

  ```bash
  for f in skills/preflight/schemas/_examples/phase_b_*.json; do
    python3 -c "import json, jsonschema; \
      schema = json.load(open('skills/preflight/schemas/phase-handoff.json')); \
      data = json.load(open('$f')); \
      jsonschema.validate(data, schema['definitions']['phase_b_output']); \
      print('OK:', '$f')"
  done
  ```

  All three must print `OK`. The error fixture must include `error_path` and omit `dispatch` and `report_path`. The dispatch fixture must include `dispatch` and omit `report_path`. The complete fixture must include `report_path` and omit `dispatch`.

- [ ] **Step 5 — Commit schema + examples.**

  ```bash
  git add skills/preflight/schemas/phase-handoff.json skills/preflight/schemas/_examples/
  git commit -m "task 1: extend phase_b/c handoff with action discriminator + dispatch shape"
  ```

  Verification: `make test-index` still green (no role schema changes, just smoke).

---

## Task 2 — Phase B coordinator rewrite (state machine, no Agent calls)

**Files:** `skills/preflight/meta-agents/sub-coordinator-phase-b.md`

The current ~385-line file is mostly correct in *what* the steps do — only *who calls Agent* changes. We're not redesigning the prompts or the dedup or the synthesis logic; we are wrapping each Agent-needing block with "build dispatch payload and return" instead of "spawn the agents myself."

- [ ] **Step 1 — Rewrite the "Pre-flight: Agent tool check" block.**

  Replace the entire section (lines 17–35) with:

  ```markdown
  ## Pre-flight: workspace state check

  This sub-coordinator no longer calls `Agent` itself. Under v0.7.0 the main session executes all dispatched `Agent` calls (parallel expert dispatch, adversarial round, synthesizer, verifier mini-round) and re-spawns this coordinator with `resume_token` set to the previous step's outcome. See `docs/specs/2026-05-03-phase-b-main-driven-dispatch.md`.

  On every spawn (first or resume), determine the next pending step by inspecting workspace state. The decision tree:

  | Workspace state | Next pending step |
  |---|---|
  | No `expert_reports/*.json` | step 7 (parallel expert dispatch) |
  | `expert_reports/*.json` exist, no `adversarial_round.json` | step 7.5 if skip-condition fails, else jump to step 8 |
  | `adversarial_round.json` exists, no `synth_result.json` | step 8 (synthesizer) |
  | `synth_result.json` exists, no `verification_round.json` | step 8.5 if skip-condition fails, else jump to step 9 |
  | All present | step 9 (render — runs inline in coordinator) |

  Do not run the legacy `ToolSearch select:Agent` probe — it is not load-bearing under v0.7.0.
  ```

- [ ] **Step 2 — Rewrite step 7 (parallel dispatch) as a dispatch emitter.**

  Replace the `### 7. Parallel dispatch` body. Keep the prompt-assembly logic (claim-citation discipline, role-KB usage discipline, artifact delimiters — all unchanged), but instead of `Launch N Agent calls in a single message`, the coordinator builds a `requests[]` array and returns a `dispatch` handoff:

  ```markdown
  ### 7. Parallel dispatch (build + emit)

  Build the per-role expert prompts exactly as documented in v0.6.x (claim-citation discipline FIRST, role-KB usage discipline SECOND, full artifact wrapped in delimiters). Persist the prompt strings in memory — do not call Agent.

  Construct the dispatch handoff:

  - `step: "7"`, `step_label: "parallel-experts"`
  - `parallelism: "parallel"` — main will single-message N Agent calls
  - `requests[]`: one per role in `roster.json`. For each role:
    - `id`: role name from `roster.json`
    - `subagent_type: "general-purpose"`
    - `model_hint`: per-task model choice — see model-assignment guidance below
    - `description: "Preflight expert: <role>"`
    - `prompt`: the assembled string (full role prompt + discipline blocks + artifact + role-KB)
    - `save_to: "<workspace_path>/expert_reports/<role>.json"`
    - `schema_ref: "schemas/expert-report.json"`
    - `on_failure: "mark_skipped"`
  - `resume_token: "post-7"`

  Return:

  ```json
  {
    "action": "dispatch",
    "workspace_path": "...",
    "last_completed_step": 6,
    "dispatch": { ... }
  }
  ```

  Do NOT update `_index.json.last_completed_step` to 7 yet — that happens after main reports success on the resume spawn (Step 1 of step-7-resume below).
  ```

  Move the model-assignment guidance (current paragraph at line 97 about "per-task, not per-role frontmatter") under this section as the model-hint reference.

- [ ] **Step 3 — Add a step-7-resume handler.**

  After the dispatch-emitter block, add:

  ```markdown
  ### 7-resume (when invoked with `resume_token == "post-7"`)

  1. Verify all expected files exist: `for r in roster.chosen: assert exists($workspace/expert_reports/<r>.json)`.
     - If a file is missing AND main marked the request `skipped` (check `_index.json.dispatch[]` for the per-request status main writes back), record it in `skipped_experts[]` and continue.
     - If a file is missing AND no skip mark: re-emit step 7 dispatch for ONLY the missing roles. Cap re-emit attempts at 2 per role; on third failure, mark skipped.
  2. Update `_index.json.last_completed_step = 7`.
  3. Proceed to step 7.5 evaluation (skip-condition + dispatch or jump).
  ```

  This is where the retry-on-malformed-JSON behaviour from v0.6.x lives now — coordinator detects malformed (or absent) results on resume and either re-emits or skips.

- [ ] **Step 4 — Repeat the emit/resume pattern for step 7.5, 8, 8.5.**

  Each of these gets the same treatment: a "build + emit" section that constructs the dispatch handoff, and a "step-N-resume" section that verifies the result file landed and decides what to do next. Skip conditions stay where they are (in the emit section — if the skip applies, jump straight to the next step's emit instead of returning a dispatch).

  Specifically:
  - **Step 7.5 emit**: gated by panel ≥ 3 AND must+should ≥ 2 (post-#16). If gated out, write `adversarial_round.json` with `skipped: true, reason`, jump to step 8 emit. Otherwise return dispatch with `step: "7.5"`, `parallelism: "parallel"`, one request per role.
  - **Step 7.5 resume**: collect post-adversarial reports, build summary, write `adversarial_round.json` with counts. Update `_index.json.last_completed_step = 7` (step 7.5 doesn't have its own step number). Proceed to step 8 emit.
  - **Step 8 emit**: drift pre-check (synchronous, no Agent — coordinator does it inline). Then emit synthesizer dispatch with `step: "8"`, `parallelism: "sequential"`, ONE request, `save_to: "<workspace>/synth_result.json"`, `on_failure: "abort"` (synthesizer failure is fatal — no graceful skip).
  - **Step 8 resume**: verify `synth_result.json` exists and is valid JSON. On malformed JSON, re-emit step 8 dispatch with a terser prompt (one retry; on second failure, write `phase-b-error.json` and return `action: "error"`). Update `_index.json.last_completed_step = 8`. Proceed to step 8.5 emit.
  - **Step 8.5 emit**: verification mini-round. Build batch (≤12 items). If skip condition (all must_fix have `code_cited`), write `verification_round.json` with `skipped: true`, jump to step 9. Otherwise emit dispatch with `step: "8.5"`, `parallelism: "parallel"`, one request per claim, `model_hint: "haiku"`.
  - **Step 8.5 resume**: collect verifier results, apply demotions per the existing v0.6.x rules, patch `synth_result.json` and write `verification_round.json`. Proceed to step 9.

- [ ] **Step 5 — Step 9 stays inline (no Agent).**

  Step 9 is pure rendering — it reads `synth_result.json` + the verification banners and writes `report.md`. No Agent call. The coordinator runs this inline on the post-8.5 resume spawn and returns `action: "complete"` with the existing fields (`report_path`, `report`, etc.).

- [ ] **Step 6 — Rewrite the "Output" section.**

  Replace the current single-shape output spec with a discriminated description (mirror schema):

  ```markdown
  ## Output — emit one of three JSON shapes and stop

  **action: "dispatch"** — most common during a Phase B run. See examples in `schemas/_examples/phase_b_dispatch.json`.

  **action: "complete"** — only emitted on the post-step-8.5 resume after step 9 rendering succeeded. Carries `report_path`, `report` (or `report_too_long: true` for files > 15000 chars), `skipped_experts`, `drift_refreshed`.

  **action: "error"** — any unrecoverable failure. Write `phase-b-error.json` to workspace and return `error_path` + `last_completed_step` (the step that failed). Main session stops; no Phase C.
  ```

- [ ] **Step 7 — Update Anti-patterns.**

  Replace the existing anti-patterns list (top of file):

  - DROP: `"I have all the expert reports in context, I'll just synthesize inline"` — no longer relevant; synthesizer is a main-session dispatch now.
  - KEEP, REWORD: `"I'll render the report from my recollection"` — still applies to step 9.
  - ADD: `"On resume, I'll trust resume_token blindly and skip the workspace-file check"` — no. Resume_token is a hint; workspace file existence is the source of truth.
  - ADD: `"Step 7 dispatch failed for one role, I'll just call Agent myself for that one"` — you cannot. Re-emit a smaller dispatch and let main retry.

- [ ] **Step 8 — Verification: sanity-render the new file.**

  ```bash
  wc -l skills/preflight/meta-agents/sub-coordinator-phase-b.md
  # expected: somewhere between 350 and 500 lines (rewrite is roughly the same size)

  grep -c "Agent(" skills/preflight/meta-agents/sub-coordinator-phase-b.md
  # expected: 0  — coordinator no longer calls Agent

  grep -c "action: \"dispatch\"\|action: \"complete\"\|action: \"error\"" skills/preflight/meta-agents/sub-coordinator-phase-b.md
  # expected: >= 6 (each action mentioned in step 6 + various contexts)
  ```

  All three checks pass → commit.

- [ ] **Step 9 — Commit.**

  ```bash
  git add skills/preflight/meta-agents/sub-coordinator-phase-b.md
  git commit -m "task 2: phase-b coordinator becomes state machine — emits dispatch, never calls Agent"
  ```

---

## Task 3 — SKILL.md Phase B handler (the loop)

**Files:** `skills/preflight/SKILL.md`

The single-spawn `Phase B` handler in `SKILL.md:64–94` becomes a loop.

- [ ] **Step 1 — Replace the Phase B handler block.**

  ```markdown
  ### Phase B — dispatch, synth, render (loop)

  Phase B coordinator under v0.7.0 returns one of `complete | dispatch | error` per spawn. Main session runs a loop: spawn coordinator → if `dispatch`, execute the requested `Agent` calls and write results to `save_to` paths → re-spawn coordinator with `resume_token` set. Loop terminates on `complete` or `error`. Worst case: 5 coordinator spawns (initial + 4 dispatch round-trips for steps 7, 7.5, 8, 8.5). Common case: 3–4.

  Pseudo-loop (the actual implementation is your normal Agent + Read + Write tool calls):

  1. **Initial spawn:**

     ```
     Agent(
       subagent_type: general-purpose,
       description: "Preflight phase B coordinator",
       prompt: <full content of skills/preflight/meta-agents/sub-coordinator-phase-b.md>
              + "\n\n## Invocation inputs\n\n"
              + JSON.stringify({
                  workspace_path: <from Phase A>,
                  gate_answers_path: <"<workspace>/gate_answers.json"> | null,
                  user_language: <same string passed to Phase A>,
                  resume_token: null
                })
              + "\n\nReturn ONLY the JSON handoff specified in the output section. No prose."
     )
     ```

  2. **Loop on response.action:**

     - `"complete"` — emit `report` (or read `report_path` if `report_too_long`), append warnings (`skipped_experts`, `drift_refreshed`), spawn Phase C. **Done.**
     - `"error"` — Read `error_path`, print verbatim. Do not spawn Phase C. **Done.**
     - `"dispatch"` — execute the dispatch (next step), then re-spawn coordinator.

  3. **Executing a dispatch:**

     Read `response.dispatch.requests[]`. If `parallelism == "parallel"`, send a single message containing N `Agent` tool calls — one per request. If `"sequential"`, send them one at a time.

     For each request:
     - Spawn `Agent(subagent_type=request.subagent_type, model=request.model_hint, description=request.description, prompt=request.prompt)`.
     - On success: Write the response to `request.save_to` verbatim.
     - On failure (timeout, malformed JSON the agent itself rejected, etc.):
       - If `request.on_failure == "mark_skipped"`: write `_index.json.dispatch[<request.id>] = {status: "skipped", reason: "<error>"}` and continue.
       - If `request.on_failure == "abort"`: stop the loop, surface error to user; do not spawn Phase C.

  4. **Re-spawn coordinator:**

     ```
     Agent(
       subagent_type: general-purpose,
       description: "Preflight phase B coordinator (resume <resume_token>)",
       prompt: <full content of skills/preflight/meta-agents/sub-coordinator-phase-b.md>
              + "\n\n## Invocation inputs\n\n"
              + JSON.stringify({
                  workspace_path: <same>,
                  gate_answers_path: <same>,
                  user_language: <same>,
                  resume_token: response.dispatch.resume_token
                })
              + "\n\nReturn ONLY the JSON handoff specified in the output section. No prose."
     )
     ```

     Loop.

  Choose model per-task: coordinator spawns are light (state inspection + dispatch construction) — Haiku suffices. Expert dispatches per `request.model_hint`.

  Parse every response against `schemas/phase-handoff.json#/definitions/phase_b_output`. On parse failure, retry the spawn once with a terser prompt; second failure → stop and surface to user.
  ```

- [ ] **Step 2 — Update Anti-patterns section.**

  Add to the existing anti-pattern list:

  - `"Phase B is taking long — let me read workspace files to check progress"` — keep this anti-pattern (already present).
  - `"The dispatch returned 5 requests, I'll fan them out as 5 separate messages instead of one"` — no. Single message with N Agent calls is the parallel-dispatch contract; separate messages serialise them and double the wall-clock.
  - `"I got a dispatch back, I'll modify the prompt to add more context"` — no. The coordinator built the prompt deliberately. Main is a dumb executor; do not edit `request.prompt`.

- [ ] **Step 3 — Verification.**

  ```bash
  grep -c "subagent_type: general-purpose" skills/preflight/SKILL.md
  # expected: 3 (Phase A, Phase B, Phase C)

  grep -c "resume_token" skills/preflight/SKILL.md
  # expected: >= 2 (initial null + re-spawn)

  grep -c "Loop on response.action\|Loop on" skills/preflight/SKILL.md
  # expected: >= 1
  ```

- [ ] **Step 4 — Commit.**

  ```bash
  git add skills/preflight/SKILL.md
  git commit -m "task 3: SKILL.md Phase B handler becomes dispatch-execute-respawn loop"
  ```

---

## Task 4 — Phase C path decision (Task 0 result branches here)

- [ ] **Step 1 — Read Task 0 outcome.**

  ```bash
  grep "BG_LOOP_OK:" skills/preflight/docs/notes/2026-05-03-phase-c-bg-loop-probe.md
  ```

- [ ] **Step 2 — Branch.**

  - `BG_LOOP_OK: true` → proceed to Task 5 (Phase C coordinator rewrite, same pattern as Task 2 but smaller).
  - `BG_LOOP_OK: false` → skip Task 5 + Task 6. Phase C stays foreground in v0.7.0 (acceptable: rubber-duck + KB compaction take ~30–60s; user UX impact small). Document the constraint in the spec and CHANGELOG.

- [ ] **Step 3 — Commit a `decisions/2026-05-03-phase-c-path.md` one-liner** noting which branch was taken.

---

## Task 5 — Phase C coordinator rewrite *(only if `BG_LOOP_OK: true`)*

Same pattern as Task 2 but degenerate (single-shot dispatches). Skip if Task 4 chose foreground.

- [ ] **Step 1 — Rewrite step 10 (rubber-duck) as dispatch emitter.**
- [ ] **Step 2 — Rewrite step 11 (KB compactor) as dispatch emitter (per role).**
- [ ] **Step 3 — Step 11 final (KB-write file I/O) stays inline in coordinator.**
- [ ] **Step 4 — Output section becomes discriminated (`complete` / `dispatch` / `error`).**
- [ ] **Step 5 — Verification: `grep -c "Agent(" skills/preflight/meta-agents/sub-coordinator-phase-c.md` returns 0.**
- [ ] **Step 6 — Commit.**

---

## Task 6 — SKILL.md Phase C handler *(only if `BG_LOOP_OK: true`)*

- [ ] **Step 1 — Replace single-spawn block with the loop, mirroring Task 3 structure.**
- [ ] **Step 2 — Verify `run_in_background: true` is preserved on every coordinator spawn within the loop.**
- [ ] **Step 3 — Commit.**

---

## Task 7 — Eval re-run + smoke test

- [ ] **Step 1 — `make test-index` passes.** (Schema-level smoke.)

- [ ] **Step 2 — Manual smoke run.** Run `/preflight` against `evals/fixtures/plan-buggy-auth/`. Compare:

  - `report.md` content vs the v0.6.5 baseline output (regenerate baseline if absent).
  - `_index.json.dispatch[]` should now contain entries for each round-trip step (7, 7.5, 8, 8.5).
  - `phase-b-error.json` should NOT exist.

  Behaviour-equivalent expectation: same verdict, same MUST/SHOULD/NICE counts ±1, same warnings (correlated_bias_risk, evidence_thinness, verification banner).

- [ ] **Step 3 — If divergence found:** investigate before declaring complete. The dispatch round-trip is meant to be transparent at the workspace/output level.

- [ ] **Step 4 — Stress test: kill mid-run.** Start `/preflight` against `evals/fixtures/plan-counter-race/`. After step 7 dispatch lands (i.e. after `expert_reports/*.json` written, before next coordinator re-spawn), kill CC. Restart, run `/preflight resume <workspace>`. Expected: coordinator detects step 7 done, emits step 7.5 dispatch, completes the run.

- [ ] **Step 5 — Commit a `evals/notes/2026-05-03-v0.7.0-smoke-results.md` summary** with timing + diff vs baseline.

---

## Task 8 — Spec doc + CHANGELOG + version bump

- [ ] **Step 1 — Update `docs/specs/2026-04-20-preflight-design.md`.**

  In §7.5 / §8 / §10–11, add the v0.7.0 round-trip note (one sentence each — these sections still describe the conceptual flow; the new wire shape is in the new spec doc, not here).

- [ ] **Step 2 — CHANGELOG entry as 0.7.0.**

  Use the v0.6.x entries as style reference. Cover: motivation (empirical harness reality, prior PRs that didn't fix it), what changed (state-machine coordinators, dispatch handoff, main-session loop), what kept (workspace layout, expert prompts, schemas additive), migration (none — old workspaces work).

- [ ] **Step 3 — Tag.**

  Maintainer-only step (do not auto-tag). Document the tag command in CHANGELOG: `git tag v0.7.0 && git push --tags`.

- [ ] **Step 4 — Commit.**

  ```bash
  git add docs/specs/ CHANGELOG.md
  git commit -m "task 8: docs + CHANGELOG bump to 0.7.0"
  ```

---

## Task 9 — Final cleanup

- [ ] **Step 1 — Remove dead code paths.** The `Pre-flight: Agent tool check` blocks in phase-b.md / phase-c.md are now informational only. Decide: leave with a "kept for v0.6.x diagnostics" comment, or delete. **Recommend: delete.** Skill is now self-consistent with v0.7.0 reality; the historical context lives in CHANGELOG and the spec doc.

- [ ] **Step 2 — Audit `meta-agents/*.md` for stale references** to "spawn this agent yourself" wording in the synthesizer / verifier / adversarial / rubber-duck files. Those still describe single-spawn semantics; update only if they reference the *coordinator's* spawn, not the agent's own behaviour.

- [ ] **Step 3 — Final commit.**

  ```bash
  git add -A
  git commit -m "task 9: final cleanup — drop stale Agent pre-flight checks, update meta-agent cross-refs"
  ```

- [ ] **Step 4 — Open the v0.7.0 PR.**

  Title: `v0.7.0: phase-b coordinator becomes state machine, main session drives Agent dispatch`

  Body should reference: spec PR #18, this implementation plan, the smoke-test results (Task 7).

---

## Anti-patterns to enforce on yourself during execution

- **"I'll skip Task 0 because I think BG loop works"** — no. Probe is cheap, hypothesis-without-data has burned us 3 times in this exact bug class.
- **"Tasks 1 and 2 are independent, I'll do them in any order"** — Task 1 (schema) must land before Task 2 (coordinator), so the coordinator's emitted handoffs validate against the schema. Otherwise the smoke test in Task 7 has no oracle.
- **"The coordinator rewrite is mechanical, I can do it in one big diff"** — no. Each step (7, 7.5, 8, 8.5) is a logically independent state-machine branch. Land them as separate sub-commits within Task 2 if possible — easier to bisect if the smoke test reveals a regression.
- **"Smoke test is flaky, I'll skip it"** — Task 7 IS the verification that V2 is behaviour-equivalent at the workspace level. If it diverges, we have a bug, not a flake.
- **"I'll bump to 1.0.0 since this feels like a real release"** — design spec defaults said 0.7.0. Stick to it unless a maintainer overrides explicitly.
