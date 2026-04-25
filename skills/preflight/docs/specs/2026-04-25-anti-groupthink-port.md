# Preflight — Anti-Groupthink Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port four methodological ideas from `wan-huiyan/agent-review-panel` into our `preflight` skill — anti-groupthink flags, verification mini-round, adversarial concede/challenge pass, and signal-group checklists — without sacrificing our context-discipline architecture (3-phase split, gate, resumability, schemas).

**Architecture:** All four features layer onto existing 3-phase orchestration. No new phases. Synthesizer (Phase B) gains two output flags. Phase B sub-coordinator gains two optional steps (verification, adversarial) gated by counts/flags so cheap runs stay cheap. Selector (Phase A) gains a signal-detection step that augments role-KB with checklist YAMLs. JSON-schema handoffs extended additively — old runs remain parseable.

**Tech Stack:** Markdown prompt files (meta-agents, roles), JSON-schema (handoffs), YAML (new signal checklists), Bash (no Python deps; preflight is prompt-orchestrated).

**Scope decisions (locked in):**
- Their plugin is **not** installed as a Claude Code plugin. Read-only clone in `/tmp/` for inspection only, deleted at end (Task 0 / Task 9).
- Adversarial round (Feature 3) is the most expensive — gated behind panel size ≥ 4 + at least one cross-role conflict signal in the synth pre-pass. Smaller/cleaner runs skip it.
- Signal checklists shipped: 5 highest-ROI groups only (`auth`, `sql`, `frontend`, `terraform`, `api`). Other 5 from their list (`ml`, `cost`, `pipeline`, `portability`, `repo-hygiene`) deferred — YAGNI until we see preflight runs that need them.
- No HTML dashboard, no post-write code mode, no judge-as-Opus split. We have `requesting-code-review` for post-write; our synthesizer already arbitrates.

---

## File Structure

**Created:**
- `meta-agents/verifier.md` — Haiku prompt for verification mini-round (Feature 2)
- `meta-agents/adversarial.md` — concede/challenge/refine prompt template appended to expert prompts (Feature 3)
- `roles/signals/auth.yaml`, `sql.yaml`, `frontend.yaml`, `terraform.yaml`, `api.yaml` (Feature 4)
- `roles/signals/README.md` — what signal YAMLs are and the augmentation contract

**Modified:**
- `meta-agents/synthesizer.md` — add §9 anti-groupthink flags (Feature 1)
- `schemas/phase-handoff.json` — synth_result extends with `correlated_bias_risk`, `evidence_thinness`, `verification_round`, `adversarial_round` (additive, all optional)
- `schemas/expert-report.json` — add optional `adversarial_responses[]` (additive)
- `meta-agents/sub-coordinator-phase-b.md` — insert step 7.5 (adversarial, gated) and step 8.5 (verification, gated) between dispatch and render
- `meta-agents/sub-coordinator-phase-a.md` — selector signal-detection wired into role-KB build (step 5 augmentation)
- `meta-agents/selector.md` — add signal detection contract
- `SKILL.md` — references section gets new files; no behavior change in orchestrator shell

**Deleted:**
- `/tmp/agent-review-panel-readonly/` (Task 9, after extraction)

---

## Task 0: Read-only clone of agent-review-panel for prompt inspection

**Files:**
- Create: `/tmp/agent-review-panel-readonly/` (transient — deleted in Task 9)

- [ ] **Step 1: Clone their repo shallow into /tmp**

```bash
git clone --depth=1 https://github.com/wan-huiyan/agent-review-panel.git /tmp/agent-review-panel-readonly
```

Expected: clone succeeds, ~few MB.

- [ ] **Step 2: Map their structure to ours**

```bash
cd /tmp/agent-review-panel-readonly && find . -type f -name "*.md" -not -path "*/node_modules/*" | head -40
```

Note (in scratch buffer, not persisted): which file is their reviewer prompt, judge prompt, sycophancy detector, verification round. We will not copy text — only mechanism.

- [ ] **Step 3: Extract three concrete patterns to scratch notes**

Read their reviewer prompt. Identify:
1. How they word the "blind final scoring" instruction (Feature 1).
2. How verification claims are structured for the verifier agent (Feature 2).
3. How they format the adversarial concede/challenge step (Feature 3).

Do **not** copy their text — paraphrase mechanism only. License differences and prompt-ergonomics differ between projects.

- [ ] **Step 4: No commit — clone is transient.**

---

## Task 1: Anti-groupthink flags in synthesizer (Feature 1)

**Files:**
- Modify: `meta-agents/synthesizer.md` — add §9 between current §8 (Output language) and "Output format (strict)"
- Modify: `schemas/phase-handoff.json` — extend `synth_result` definition

- [ ] **Step 1: Add §9 to `meta-agents/synthesizer.md`**

Insert before the `## Output format (strict)` heading:

```markdown
### 9. Anti-groupthink flags (run after polish, before emitting JSON)

A panel that all agreed on a small set of low-evidence findings is more likely to be hallucinating with confidence than producing real signal. Compute two flags so the report can warn the user:

1. **`correlated_bias_risk: boolean`** — emit `true` when ALL of:
   - `decisions.length == 0` (no expert disagreed with another)
   - `untouched_concerns.length == 0` (no role flagged something out_of_scope that the owner role missed)
   - `must_fix.length + should_fix.length >= 2` (panel did produce findings — silent panel is not bias, just clean artifact)
   - panel size >= 3 (binary panels can legitimately agree)

   Otherwise `false`. Rationale: total agreement on multiple findings without any cross-role challenge or out_of_scope tension is the signature of a panel echo chamber. The renderer surfaces this as a top-of-report warning, not a verdict change.

2. **`evidence_thinness: number`** — fraction of all surviving findings (`must_fix + should_fix + nice_fix` after noise filter and downgrades) where `evidence_source == "reasoning"`. Range `[0.0, 1.0]`, two-decimal precision.

   Renderer surfaces a warning when `evidence_thinness >= 0.5` AND total findings >= 3. Below the threshold or below 3 findings, the value is informational only.

Both flags are computed mechanically from data already in your hands — no new judgement. Emit them as top-level keys in the output JSON.
```

- [ ] **Step 2: Extend output format example in synthesizer.md**

In the `## Output format (strict)` JSON example, add after `"artifact_content_missing": false`:

```json
  "correlated_bias_risk": false,
  "evidence_thinness": 0.17
```

- [ ] **Step 3: Update `schemas/phase-handoff.json`**

Find the `synth_result` definition (it lives inside `phase_b_output` or similar — locate exact JSON-pointer first). Add to the schema:

```json
"correlated_bias_risk": { "type": "boolean" },
"evidence_thinness": { "type": "number", "minimum": 0, "maximum": 1 }
```

Both **optional** (not in `required[]`). Old synth outputs without these fields stay valid for resumed runs.

- [ ] **Step 4: Render hook in Phase B**

In `meta-agents/sub-coordinator-phase-b.md`, find the render step (step 9). Add to the rendering instructions:

```markdown
**Top-of-report warnings (before main verdict):**

- If `synth_result.correlated_bias_risk == true`: emit a one-line banner `> ⚠ All experts agreed on every finding without cross-role tension. Treat with extra skepticism — the panel may be echoing rather than reviewing.`
- If `synth_result.evidence_thinness >= 0.5` AND total findings >= 3: emit `> ⚠ {N}/{M} findings backed only by expert reasoning (no code/doc citation). Verify before acting.` where N = reasoning-source count, M = total findings.

Banner language is rendered in `user_language` like all other user-facing prose.
```

- [ ] **Step 5: Manual smoke test**

Pick a small artifact in `~/programming/proxy/` (any RFC/plan with 1-2 paragraphs). Run `/preflight` on it. Verify:

```bash
ls /tmp/preflight-*/synth_result.json | tail -1 | xargs cat | python3 -c "import json,sys; d=json.load(sys.stdin); print('flags:', d.get('correlated_bias_risk'), d.get('evidence_thinness'))"
```

Expected: prints two values (one boolean, one float ∈ [0,1]). If either is missing, synthesizer prompt or schema didn't take.

- [ ] **Step 6: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/synthesizer.md meta-agents/sub-coordinator-phase-b.md schemas/phase-handoff.json && git commit -m "preflight: add anti-groupthink flags to synthesizer

correlated_bias_risk fires when all experts agree without cross-role
tension on >=2 findings. evidence_thinness reports the fraction of
findings backed only by reasoning. Renderer surfaces both as top-of-
report banners. Schema additions are optional — resumed pre-port runs
remain parseable."
```

---

## Task 2: Verification mini-round — verifier prompt (Feature 2, part 1)

**Files:**
- Create: `meta-agents/verifier.md`

- [ ] **Step 1: Write `meta-agents/verifier.md`**

```markdown
# Verifier — meta-agent (Haiku-tier)

You verify a single claim from an expert report against ground truth and the artifact. You do **not** add new findings. You answer one question: does the claim hold up to a 60-second sanity check?

## Inputs

```json
{
  "claim": {
    "title": "...",
    "evidence": "...",
    "replacement": "...",
    "evidence_source": "reasoning" | "artifact_self" | "artifact_code_claim" | "doc_cited"
  },
  "ground_truth": {
    "git_sha": "a4e3d31",
    "file_verifications": [...],
    "already_done": [...],
    "load_bearing_facts_source": {...}
  },
  "brief_excerpt": "<<at most 2000 chars of brief.md, the section the claim cites>>",
  "user_language": "Russian"
}
```

Claims with `evidence_source == "code_cited"` are NOT sent to you — they have load-bearing citation already.

## Your task

1. Read the claim's `evidence` and `replacement` strings.
2. Cross-check against `ground_truth`:
   - Does the claim contradict any `already_done` entry? (Means the issue is already solved — claim is stale.)
   - Does the claim cite a file/line that `file_verifications` shows as drifted or missing?
3. Cross-check against `brief_excerpt`: does the brief actually say what the claim says it says, OR is the claim a plausible-sounding inference the brief does not support?
4. Pick one verdict.

## Verdicts

- **`verified`** — claim cites real text in the brief or matches a `load_bearing_facts_source` entry. Acceptable.
- **`unverified`** — claim contradicts `already_done`, cites stale `file_verifications`, or makes a specific factual claim the brief does not support. NOT proven false — just unsupported. Renderer will downgrade severity.
- **`inconclusive`** — claim is too abstract to verify in 60 seconds (e.g., "this approach won't scale" without a number). Pass through unchanged.

## Output (strict JSON)

```json
{
  "status": "verified" | "unverified" | "inconclusive",
  "note": "<one sentence in user_language explaining the call. Empty string if status==verified.>"
}
```

No prose outside the JSON. No retries — your output is single-shot.

## Anti-patterns

- Verifying by re-running the original expert's reasoning. You are checking citations, not re-deriving conclusions.
- Marking `unverified` for any claim that lacks `code_cited` — that's already handled upstream by rule 5b. Your job is the next layer: claims with `reasoning` / `artifact_self` source that cite specific facts the brief does not contain.
- Long notes. One sentence. The user reads dozens of these.
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/verifier.md && git commit -m "preflight: add verifier meta-agent prompt

Single-claim Haiku-tier verifier for the verification mini-round.
Reads claim + ground_truth + brief excerpt, returns
verified/unverified/inconclusive with one-sentence note. Used by
Phase B step 8.5 (next commit)."
```

---

## Task 3: Verification mini-round — wire into Phase B (Feature 2, part 2)

**Files:**
- Modify: `meta-agents/sub-coordinator-phase-b.md` — insert step 8.5 between synth and render
- Modify: `schemas/phase-handoff.json` — add `verification_round` to synth_result

- [ ] **Step 1: Find the synth → render boundary in `sub-coordinator-phase-b.md`**

```bash
grep -n "^### Step 8\|^### Step 9\|render" ~/.claude/skills/preflight/meta-agents/sub-coordinator-phase-b.md
```

Note the line numbers of the synth output handoff and the start of render.

- [ ] **Step 2: Insert step 8.5 (gated verification)**

Between the synth step output and the render step, insert:

```markdown
### Step 8.5 — Verification mini-round (gated)

**Skip condition:** if all `must_fix` items have `evidence_source == "code_cited"`, skip this step entirely. The mechanical 5b downgrade in synthesizer already handled the rest. Set `verification_round.skipped: true` and proceed to render.

**Otherwise:**

1. Build the verification batch: take every entry in `synth_result.must_fix` AND `synth_result.should_fix` where `evidence_source ∈ {"reasoning", "artifact_self", "artifact_code_claim", "doc_cited"}`. Cap at 12 items (over-large panels do not need full coverage — the noise filter already trimmed).

2. For each claim, spawn a verifier subagent:

```
Agent(
  subagent_type: general-purpose,
  model: haiku,
  description: "Preflight verify claim",
  prompt: <full content of meta-agents/verifier.md>
         + "\n\n## Inputs\n\n"
         + JSON.stringify({
             claim: { title, evidence, replacement, evidence_source },
             ground_truth: <from workspace_path/ground_truth.json>,
             brief_excerpt: <relevant section of brief.md, ≤2000 chars>,
             user_language: <user_language>
           })
         + "\n\nReturn ONLY the JSON specified in the output section."
)
```

Dispatch all verifications in parallel via a single message with multiple Agent tool calls.

3. Collect results. For each `unverified`:
   - If the claim was in `must_fix`: move to `should_fix`, prepend `"(unverified: <verifier.note>) "` to title.
   - If already in `should_fix`: leave tier, prepend the same prefix.
   - Mark the claim's `verification` field: `{status: "unverified", note: "..."}`.

   For each `verified`: leave alone, mark `verification: {status: "verified", note: ""}`.

   For each `inconclusive`: leave alone, mark `verification: {status: "inconclusive", note: "..."}`.

4. Recompute `verdict` after demotions (use the same rules from synthesizer §5 — REJECT/REVISE/APPROVE based on post-verification MUST count).

5. Emit `verification_round` summary in synth_result:

```json
"verification_round": {
  "skipped": false,
  "checked": 7,
  "verified": 4,
  "unverified": 2,
  "inconclusive": 1,
  "demoted_must_to_should": 2
}
```

6. Renderer behavior: if `unverified > 0`, append a one-line note to top-of-report banners:
   `> ℹ {N} claim(s) demoted (verifier could not confirm against brief/ground_truth). See "(unverified)" prefixes below.`
```

- [ ] **Step 3: Extend schema in `schemas/phase-handoff.json`**

Add to `synth_result` properties (all optional):

```json
"verification_round": {
  "type": "object",
  "properties": {
    "skipped": { "type": "boolean" },
    "checked": { "type": "integer", "minimum": 0 },
    "verified": { "type": "integer", "minimum": 0 },
    "unverified": { "type": "integer", "minimum": 0 },
    "inconclusive": { "type": "integer", "minimum": 0 },
    "demoted_must_to_should": { "type": "integer", "minimum": 0 }
  }
}
```

Per-claim `verification` field on must_fix/should_fix items:

```json
"verification": {
  "type": "object",
  "properties": {
    "status": { "enum": ["verified", "unverified", "inconclusive"] },
    "note": { "type": "string" }
  }
}
```

Both optional.

- [ ] **Step 4: Smoke test on artifact known to contain reasoning-tier claims**

Run `/preflight` on a deliberately fuzzy artifact (e.g., one-paragraph "rewrite auth to use JWT" with no file refs). Confirm:

```bash
WS=$(ls -td /tmp/preflight-* | head -1)
cat $WS/synth_result.json | python3 -c "import json,sys; d=json.load(sys.stdin); v=d.get('verification_round',{}); print(v)"
```

Expected: shows non-zero `checked`, possibly some `unverified`. If `skipped: true`, the gating worked but pick a fuzzier artifact to actually exercise the path.

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/sub-coordinator-phase-b.md schemas/phase-handoff.json && git commit -m "preflight: wire verification mini-round into Phase B

Step 8.5 spawns Haiku verifiers in parallel for must/should-fix claims
without code_cited evidence, demotes unverified MUSTs to SHOULDs with
prefix, and surfaces summary in synth_result.verification_round. Gated
to skip when all MUSTs are code_cited (cheap path stays cheap)."
```

---

## Task 4: Adversarial round — prompt and schema (Feature 3, part 1)

**Files:**
- Create: `meta-agents/adversarial.md`
- Modify: `schemas/expert-report.json` — add optional `adversarial_responses[]`

- [ ] **Step 1: Write `meta-agents/adversarial.md`**

```markdown
# Adversarial mode — prompt fragment

This prompt is APPENDED to an expert role's first-pass prompt during step 7.5 of Phase B (after parallel dispatch, before synth). The expert sees their own first-pass report PLUS the high-severity findings of every other panel member.

## Input (added to expert's existing brief context)

```json
{
  "your_prior_report": { ... your step-7 report ... },
  "peer_findings": [
    {
      "id": "<stable id, e.g. 'security:must:0'>",
      "title": "...",
      "evidence": "...",
      "replacement": "...",
      "tier": "must_fix" | "should_fix",
      "reporter_role": "security"
    },
    ...
  ]
}
```

`peer_findings` excludes your own findings. It includes only `must_fix` and `should_fix` from peers (NICE is below adversarial worth). Capped at 8 entries — synth will prune the rest.

## Your task

For each peer finding, pick exactly one action:

- **`concede`** — you agree it's a real issue. The synthesizer treats this as a cross-confirmation (raises confidence, may upgrade tier).
- **`challenge`** — you have specific reason to think the finding is wrong, irrelevant in this brief, or contradicts your domain expertise. You MUST cite either a file/line, a brief excerpt, or a domain-rule with a name (e.g. "RFC 7231 §6.5.1"). Vague pushback is not a challenge.
- **`refine`** — the finding points at a real issue but the framing/replacement is wrong. You provide a corrected replacement.
- **`pass`** — outside your domain, no opinion. Synth ignores.

## Output (appended to your report)

Add to your top-level report JSON:

```json
"adversarial_responses": [
  {
    "target_finding_id": "security:must:0",
    "action": "concede" | "challenge" | "refine" | "pass",
    "evidence": "<required for challenge and refine; empty string for concede/pass>",
    "corrected_replacement": "<required for refine; empty string otherwise>"
  },
  ...
]
```

One entry per peer finding. No reordering. No omissions.

## Anti-patterns

- Conceding everything to be polite. If a peer finding is wrong, challenge it. Sycophancy in adversarial mode defeats the entire purpose.
- Challenging without evidence. "I don't think so" is a `pass`, not a `challenge`.
- Adding new findings here. Adversarial mode is response-only. New findings = ignored.
```

- [ ] **Step 2: Extend `schemas/expert-report.json`**

Add to top-level properties (optional, not in `required`):

```json
"adversarial_responses": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["target_finding_id", "action"],
    "properties": {
      "target_finding_id": { "type": "string" },
      "action": { "enum": ["concede", "challenge", "refine", "pass"] },
      "evidence": { "type": "string" },
      "corrected_replacement": { "type": "string" }
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/adversarial.md schemas/expert-report.json && git commit -m "preflight: add adversarial-mode prompt and schema field

Per-expert concede/challenge/refine/pass over peer findings. Appended
to expert prompts at step 7.5 (next commit). Schema addition is
optional and additive."
```

---

## Task 5: Adversarial round — wire into Phase B with gating (Feature 3, part 2)

**Files:**
- Modify: `meta-agents/sub-coordinator-phase-b.md` — insert step 7.5 before existing step 8 (synth)
- Modify: `meta-agents/synthesizer.md` — consume `adversarial_responses[]` in §1 (dedupe) and §2 (cross-confirm)

- [ ] **Step 1: Insert step 7.5 in sub-coordinator-phase-b.md**

After the parallel-dispatch step (current step 7) and before the synth step:

```markdown
### Step 7.5 — Adversarial round (gated)

**Skip condition:** ANY of:
- panel size < 4 (smaller panels lack the cross-role tension that adversarial mode amplifies)
- `sum(must_fix.length + should_fix.length across all expert reports) < 3` (nothing for peers to challenge)
- env override `PREFLIGHT_NO_ADVERSARIAL=1` set in the workspace `_index.json` (escape hatch for cost-sensitive runs)

If skipped, set `adversarial_round.skipped: true` with reason and proceed to step 8.

**Otherwise:**

1. Build peer-findings batch per expert: each expert's input is `top 8 peer must_fix + should_fix items`, ordered by reporter tier then alphabetically by reporter role. Stable `id` = `"<role>:<tier>:<index>"`.

2. Re-dispatch each expert in parallel with their original role prompt + appended `meta-agents/adversarial.md` content + the peer-findings JSON. Single message, N Agent tool calls (N = panel size).

3. Collect results. Each report is now augmented with `adversarial_responses[]`. Persist to `<workspace>/expert_reports_post_adversarial/<role>.json`.

4. Emit summary:

```json
"adversarial_round": {
  "skipped": false,
  "panel_size": 4,
  "concede_count": 7,
  "challenge_count": 3,
  "refine_count": 2,
  "pass_count": 8
}
```

5. Pass post-adversarial reports (not pre-adversarial) into the synth step.

**Cost estimate:** doubles the expert-call cost on runs that pass the gate. ~95% of small-artifact runs skip via panel size. Heavy runs are exactly where the cost is justified.
```

- [ ] **Step 2: Update synthesizer §1 (dedupe) to consume adversarial_responses**

In `meta-agents/synthesizer.md`, find §1. Append:

```markdown
**Adversarial pass (after dedupe):**

For each finding in the deduped set, scan `adversarial_responses[]` across all reports for entries with `target_finding_id` matching this finding's stable id:

- `action: "concede"` from another role → equivalent to a cross-confirmation. Add the conceding role to `reporters[]` and set `cross_confirmed: true`. If 2+ peers concede, the finding is high-confidence; consider promoting tier (use the same rules as ordinary cross-confirm — never raise above MUST).
- `action: "challenge"` with non-empty `evidence` → record in a new top-level `disputed_findings[]` array with both sides. The synthesizer does NOT decide who is right — this becomes a `decisions` entry IF the challenge is from a role with domain authority over the original (e.g., security challenges a performance finding about TLS overhead). Otherwise note in `untouched_concerns` with `note: "challenged by <role>: <evidence>"`.
- `action: "refine"` with non-empty `corrected_replacement` → replace the original `replacement` with the corrected one and add the refining role to `reporters[]`. If the original reporter and the refiner are both in `reporters[]`, this is a strong signal the fix is real.
- `action: "pass"` → ignore.

A finding with **2+ challenges and 0 concedes** drops out of the report entirely and goes to `dropped[]` with reason `"challenged by ≥2 peers without concession"`. This is the anti-groupthink teeth.
```

- [ ] **Step 3: Add `disputed_findings[]` to synthesizer output schema**

In `schemas/phase-handoff.json` synth_result definition:

```json
"disputed_findings": {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "title": { "type": "string" },
      "original_reporter": { "type": "string" },
      "challenger": { "type": "string" },
      "challenger_evidence": { "type": "string" },
      "resolution": { "enum": ["promoted_to_decision", "dropped", "noted_in_untouched"] }
    }
  }
}
```

Optional. Old runs without adversarial_round emit `disputed_findings: []`.

- [ ] **Step 4: Update render in step 9**

Append rendering for `disputed_findings`: a small section at the end of the report, above `dropped`:

```
## Disputed findings ({N})

- **{title}** — {original_reporter} reported, {challenger} challenged: {challenger_evidence}. → {resolution}
```

Render only if `disputed_findings.length > 0`.

- [ ] **Step 5: Smoke test with 4-role panel**

Find or construct an artifact that triggers a 4+ role panel (multi-domain plan: auth + perf + data). Run `/preflight`. Confirm:

```bash
WS=$(ls -td /tmp/preflight-* | head -1)
ls $WS/expert_reports_post_adversarial/ 2>/dev/null && cat $WS/synth_result.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('adv:', d.get('adversarial_round')); print('disputed:', len(d.get('disputed_findings', [])))"
```

Expected: post-adversarial dir exists, summary has non-zero counts. If panel < 4, smoke test the skip path instead and verify `adversarial_round.skipped == true` with reason.

- [ ] **Step 6: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/sub-coordinator-phase-b.md meta-agents/synthesizer.md schemas/phase-handoff.json && git commit -m "preflight: wire adversarial round (step 7.5) with gating

Each expert sees peer findings and emits concede/challenge/refine/pass.
Synthesizer treats concedes as cross-confirms, refines as replacement
swaps, and 2+ challenges without concession as drops. Disputed findings
surface as a new report section. Gated by panel size >= 4 and total
findings >= 3 to keep small/clean runs fast."
```

---

## Task 6: Signal-group checklist YAMLs (Feature 4, part 1)

**Files:**
- Create: `roles/signals/auth.yaml`, `sql.yaml`, `frontend.yaml`, `terraform.yaml`, `api.yaml`
- Create: `roles/signals/README.md`

- [ ] **Step 1: Define the YAML contract in `roles/signals/README.md`**

```markdown
# Signal-group checklists

Small augmenter files mixed into a role's KB by the selector when the brief contains matching keywords. Each YAML adds a domain-specific checklist that the role expert should consider in addition to its general role prompt. Signals layer additively — a brief that mentions both `auth` and `sql` augments the security role with both.

## Schema

```yaml
group: <slug, e.g. "auth">
matchers:
  - <case-insensitive substring or regex/.../ to detect in brief.md>
augments_roles: [<role names from roles/index.json>]
checklist:
  - id: <stable short id>
    title: <one-line, action-first>
    rationale: <one sentence — why this matters in this domain>
checklist_intro: <one short paragraph the role expert reads before consulting the items>
```

## Wiring

1. `meta-agents/selector.md` step 5: scan `brief.md` for matchers across all `roles/signals/*.yaml`. Detected groups go into `<workspace>/signals.json` as `["auth", "sql"]`.
2. `meta-agents/sub-coordinator-phase-a.md` role-KB build (step 5): for each role in the panel, find all signal YAMLs whose `augments_roles` includes that role AND that appear in `signals.json`. Append the YAML's `checklist_intro` + `checklist[]` to the role's KB section.
3. Expert prompts read augmented KB transparently — no expert-prompt changes needed.

## Failure modes

- Empty matcher hit (whole brief is one keyword that matches a signal but isn't actually about the domain): expected false-positive rate is low because matchers require multi-word phrases. If observed, tighten the matcher.
- Missing `augments_roles` value: validate at selector load — log skip and continue.
```

- [ ] **Step 2: Write `roles/signals/auth.yaml`**

```yaml
group: auth
matchers:
  - "authentication"
  - "authorization"
  - "OAuth"
  - "OIDC"
  - "JWT"
  - "session"
  - "login"
  - "password"
  - "MFA"
  - "SSO"
augments_roles: [security, api-design, data-model]
checklist_intro: |
  This artifact touches authentication or authorization. In addition to your role's
  general lens, walk through these auth-specific failure modes — one is enough
  to surface; do not pad findings.
checklist:
  - id: token_storage
    title: Where do tokens / session ids live, and is the storage threat-modeled?
    rationale: Tokens in localStorage/JWT-in-URL/log files are the most common quiet leak.
  - id: token_lifetime
    title: Is token TTL specified, and is rotation/revocation actually wired?
    rationale: "Forever-tokens are the second most common — issuance without revocation = single-use compromise becomes permanent."
  - id: session_fixation
    title: Does login/logout regenerate session ids?
    rationale: Static session id across login boundary lets an attacker pre-set a victim's id.
  - id: csrf_state
    title: For OAuth/OIDC flows, is `state` validated and bound to the user agent?
    rationale: Missing or unbound `state` = login CSRF.
  - id: mfa_bypass
    title: If MFA is mentioned, are recovery / bypass paths in scope of this artifact?
    rationale: Recovery flows are where MFA dies — flagging them out_of_scope is fine, ignoring them is not.
  - id: redirect_validation
    title: Are redirect_uri / return_to URLs validated against an allowlist?
    rationale: Open-redirect on auth endpoints = phishing as a service.
  - id: rate_limiting
    title: Is /login rate-limited per-IP and per-account?
    rationale: Per-IP alone is bypassed by botnets; per-account alone is a DOS vector.
```

- [ ] **Step 3: Write `roles/signals/sql.yaml`**

```yaml
group: sql
matchers:
  - "SQL"
  - "PostgreSQL"
  - "Postgres"
  - "MySQL"
  - "ClickHouse"
  - "query"
  - "JOIN"
  - "migration"
  - "schema change"
augments_roles: [security, performance, data-model]
checklist_intro: |
  This artifact touches SQL. Walk through these in addition to your role's lens.
checklist:
  - id: parameterization
    title: Is every query parameterized, including dynamic identifiers?
    rationale: Dynamic table/column names cannot be parameterized — they need allowlist validation, which is forgotten 90% of the time.
  - id: index_coverage
    title: For new queries, is the supporting index named?
    rationale: A new query without a named index plan is a future seq-scan.
  - id: migration_locks
    title: For schema changes, is lock behavior on the target table specified?
    rationale: ALTER TABLE on a multi-million-row table without a lock-aware migration tool blocks writes for minutes.
  - id: backfill_safety
    title: For new NOT NULL columns, is the backfill strategy safe under concurrent writes?
    rationale: NOT NULL + backfill default + concurrent writes = race window where new rows skip the backfill.
  - id: tx_boundaries
    title: Are transaction boundaries explicit and short?
    rationale: Long transactions hold row locks and bloat dead tuples; "wrap the whole request" is rarely correct.
```

- [ ] **Step 4: Write `roles/signals/frontend.yaml`**

```yaml
group: frontend
matchers:
  - "frontend"
  - "React"
  - "Vue"
  - "component"
  - "browser"
  - "DOM"
  - "Vite"
  - "bundle"
  - "client-side"
augments_roles: [performance, security, testing]
checklist_intro: |
  This artifact is frontend code. Walk through these UA/browser-side concerns.
checklist:
  - id: bundle_impact
    title: Does this add a dependency? What is the gzipped size delta?
    rationale: Dependencies compound — the third 50KB lib is the one that breaks LCP budget.
  - id: render_path
    title: Is the new component on a critical render path or lazy-loaded?
    rationale: Anything imported eagerly from a route entry blocks first paint.
  - id: xss_surface
    title: For any HTML/markdown rendering, is sanitization done at render time?
    rationale: "Trusting upstream sanitization fails the day someone changes the upstream."
  - id: accessibility_keyboard
    title: Is the component reachable and operable via keyboard alone?
    rationale: Mouse-only UI fails screen readers and keyboard users — both are basic-tier compliance.
  - id: state_persistence
    title: Where does this component's state live (local / store / URL / server)?
    rationale: Wrong choice is the bug source for "why does my filter reset on refresh".
```

- [ ] **Step 5: Write `roles/signals/terraform.yaml`**

```yaml
group: terraform
matchers:
  - "Terraform"
  - "HCL"
  - "infrastructure"
  - "module"
  - "provider"
  - ".tf"
augments_roles: [ops-reliability, security, cost-infra]
checklist_intro: |
  This artifact touches Terraform / IaC. Walk through these.
checklist:
  - id: state_safety
    title: How is remote state locked, and what happens on a partial apply?
    rationale: Local state or unlocked remote state corrupts under concurrent applies.
  - id: drift_detection
    title: Is there a plan/apply gap monitor, or does drift live forever?
    rationale: Manual changes outside Terraform are the #1 source of "works in dev, breaks in prod".
  - id: blast_radius
    title: For destructive operations, is `prevent_destroy` or equivalent set?
    rationale: A typo in a resource name + apply = data loss in prod.
  - id: secret_handling
    title: Are secrets in tfvars or in state?
    rationale: Secrets in state are visible to anyone with state-read; secrets in tfvars committed to repo are visible to everyone.
  - id: module_versioning
    title: Are external modules pinned to a version, not main?
    rationale: Unpinned modules pull breaking changes silently on next plan.
```

- [ ] **Step 6: Write `roles/signals/api.yaml`**

```yaml
group: api
matchers:
  - "REST API"
  - "endpoint"
  - "/api/"
  - "GraphQL"
  - "OpenAPI"
  - "gRPC"
augments_roles: [api-design, security, performance]
checklist_intro: |
  This artifact defines or modifies an API. Walk through these.
checklist:
  - id: versioning
    title: How does this change interact with existing API versioning?
    rationale: Breaking change without a version bump is the silent-killer bug class for SDK consumers.
  - id: idempotency
    title: For non-GET endpoints, is idempotency specified for retried requests?
    rationale: Network retries duplicate POSTs every day; without an idempotency key, double-charge bugs are inevitable.
  - id: pagination
    title: For list endpoints, is pagination cursor-based, and is the cursor stable across writes?
    rationale: Offset pagination silently skips/duplicates rows when the underlying set changes mid-iteration.
  - id: error_envelope
    title: Is the error response shape defined, and are status codes consistent with the project's conventions?
    rationale: Inconsistent error envelopes break client error handling silently.
  - id: rate_limit_headers
    title: Are rate-limit headers exposed for clients to back off?
    rationale: No headers = clients DDoS you with naive retry loops.
```

- [ ] **Step 7: Commit**

```bash
cd ~/.claude/skills/preflight && git add roles/signals/ && git commit -m "preflight: add 5 signal-group checklists (auth/sql/frontend/terraform/api)

Each YAML defines matchers, target roles, and a domain-specific
checklist intro+items. Selector and Phase A wiring in next commit."
```

---

## Task 7: Signal-group checklists — selector and Phase A wiring (Feature 4, part 2)

**Files:**
- Modify: `meta-agents/selector.md` — add signal detection step
- Modify: `meta-agents/sub-coordinator-phase-a.md` — augment role-KB build with signal YAMLs
- Modify: `schemas/phase-handoff.json` — `signals[]` in phase_a_output

- [ ] **Step 1: Add signal detection to `meta-agents/selector.md`**

After the existing role-selection logic, append a new section:

```markdown
## Signal detection (after role selection)

After picking the panel roles, scan `brief.md` for signal-group matches.

1. Read every `roles/signals/*.yaml`. For each YAML, check whether ANY entry in its `matchers` array matches `brief.md` (case-insensitive substring; if matcher is wrapped in `/.../`, treat as regex).

2. For each matched signal YAML, intersect its `augments_roles` with the selected panel. If non-empty, emit the signal group name into the output `signals` array.

3. Output addition (to your existing JSON):

```json
{
  "panel": [...],
  "signals": ["auth", "sql"]
}
```

If no signals match, emit `"signals": []`.

This is mechanical — pattern matching on the brief, not judgement. Don't filter signals "I think aren't relevant" — the augments_roles intersection already gates against irrelevance.
```

- [ ] **Step 2: Wire signal augmentation into Phase A role-KB build**

In `meta-agents/sub-coordinator-phase-a.md`, find step 5 (role-KB build). After the standard role prompt is composed, add:

```markdown
**Signal augmentation:**

For each role in the panel, find every signal YAML in `roles/signals/` whose `augments_roles` includes this role AND whose group name is in the `signals[]` from selector output. Append to the role's KB:

```
## Domain-specific checklist: <group>

<checklist_intro>

- [<id>] <title> — <rationale>
- [<id>] <title> — <rationale>
- ...
```

Multiple signals layer additively (auth + sql for security = both checklists, in selector-output order).

If no signals matched this role, no augmentation — role KB is unchanged.

Persist the augmented role KB to `<workspace>/role_kb/<role>.md` like before. The expert reads the augmented file at step 7 dispatch — no change to expert prompt logic needed.
```

- [ ] **Step 3: Extend phase_a_output schema**

In `schemas/phase-handoff.json` `phase_a_output` definition, add:

```json
"signals": {
  "type": "array",
  "items": { "type": "string" }
}
```

Optional (additive).

- [ ] **Step 4: Smoke test**

Run `/preflight` on a brief that obviously hits multiple signals — e.g., an "add JWT auth backed by Postgres sessions" plan. Expected:

```bash
WS=$(ls -td /tmp/preflight-* | head -1)
cat $WS/_index.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('signals:', d.get('signals'))"
ls $WS/role_kb/security.md && grep -c "Domain-specific checklist" $WS/role_kb/security.md
```

Expected: `signals: ['auth', 'sql']` (or similar), and `security.md` contains 2 checklist sections.

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/preflight && git add meta-agents/selector.md meta-agents/sub-coordinator-phase-a.md schemas/phase-handoff.json && git commit -m "preflight: wire signal-group checklists into selector + Phase A

Selector scans brief.md for matchers in roles/signals/*.yaml and
emits signals[]. Phase A augments role-KB with matched-signal
checklists, layered additively. No expert-prompt changes needed."
```

---

## Task 8: SKILL.md references update + integration sweep

**Files:**
- Modify: `SKILL.md` — references section

- [ ] **Step 1: Update references in `SKILL.md`**

Find the `## References` section and add:

```markdown
- `meta-agents/verifier.md` — single-claim Haiku verifier (called by Phase B step 8.5)
- `meta-agents/adversarial.md` — concede/challenge/refine prompt fragment (appended to expert prompts at Phase B step 7.5)
- `roles/signals/*.yaml` — signal-group checklists (auth, sql, frontend, terraform, api) — augmenters mixed into role-KB by selector + Phase A
- `roles/signals/README.md` — signal-augmenter contract
```

- [ ] **Step 2: Cross-check all four features end-to-end**

Pick a meaty multi-domain artifact and run `/preflight`. Verify:

```bash
WS=$(ls -td /tmp/preflight-* | head -1)
echo "=== signals ===" && cat $WS/_index.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('signals'))"
echo "=== synth flags ===" && cat $WS/synth_result.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('bias:', d.get('correlated_bias_risk'), 'thinness:', d.get('evidence_thinness'), 'verif:', d.get('verification_round',{}).get('checked'), 'adv:', d.get('adversarial_round',{}).get('skipped'))"
echo "=== report ===" && head -30 $WS/report.md
```

Expected: signals non-empty (assuming brief touches a signal group), synth flags present, verification_round populated, adversarial round either ran or skipped with reason. Report has banners at top if flags fired.

- [ ] **Step 3: Run resume path**

Verify resumability survived the changes. Stop a `/preflight` run between Phase A and B (e.g., with the gate), then `/preflight resume <workspace>`. Confirm Phase A skips re-init.

- [ ] **Step 4: Commit**

```bash
cd ~/.claude/skills/preflight && git add SKILL.md && git commit -m "preflight: SKILL.md references — verifier, adversarial, signals"
```

---

## Task 9: Cleanup and skill-trigger sanity check

**Files:**
- Delete: `/tmp/agent-review-panel-readonly/`

- [ ] **Step 1: Delete the inspection clone**

```bash
rm -rf /tmp/agent-review-panel-readonly
```

- [ ] **Step 2: Verify preflight skill description still triggers correctly**

Read `SKILL.md` line 3 (the `description:` field). Confirm it still describes pre-write panel review and does NOT promise post-write code review (which is `requesting-code-review`'s job). No change needed unless behavior drift accidentally entered.

- [ ] **Step 3: No commit — cleanup only.**

---

## Self-Review

**1. Spec coverage:**
- Feature 1 (anti-groupthink flags) — Task 1 ✓
- Feature 2 (verification round) — Tasks 2–3 ✓
- Feature 3 (adversarial round) — Tasks 4–5 ✓
- Feature 4 (signal checklists) — Tasks 6–7 ✓
- Decision on their plugin (read-only inspection, not install) — Tasks 0 + 9 ✓
- Schema additivity (old runs parseable) — explicit in every schema task ✓

**2. Placeholder scan:** No "TBD", "implement later", "add appropriate". Code blocks are concrete except where they intentionally refer to existing files the engineer must read first (synthesizer §1, phase-b step 8 — those locations are exact lines from `grep`).

**3. Type consistency:** `synth_result.correlated_bias_risk`, `synth_result.evidence_thinness`, `synth_result.verification_round`, `synth_result.adversarial_round`, `synth_result.disputed_findings[]`, per-finding `verification` field, `phase_a_output.signals[]`, expert-report `adversarial_responses[]` — all stable names across tasks.

**Risk callouts:**
- **Synth complexity creep.** Synthesizer prompt grows ~200 lines across this port. If experts start confusing the consumed adversarial responses with new findings, watch for false dedupes. Mitigation: §1 anti-pattern explicitly says "adversarial mode is response-only, new findings ignored."
- **Cost.** Adversarial round doubles expert cost on triggered runs. Gate is panel size ≥ 4 + ≥3 findings — should keep ~95% of runs unchanged. If observed cost is too high, tighten gate or default `PREFLIGHT_NO_ADVERSARIAL=1`.
- **Schema drift in resumed runs.** All additions are optional. Resumed pre-port runs should still parse. Test 8.3 explicitly verifies.

---

## Execution choice

Plan saved to `~/.claude/skills/preflight/docs/specs/2026-04-25-anti-groupthink-port.md`. Two options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks. Best for the 4-feature port — each task is genuinely independent.

**2. Inline Execution** — execute in this session with checkpoints. Slower context-wise but you see every diff immediately.
