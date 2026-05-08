# AskUserQuestion gate — design note

**Status:** implemented in `feat/ask-user-question-gate`.
**Date:** 2026-05-08.
**Scope:** Phase A → main-session gate handoff. No changes to Phase B/C, expert prompts, or schemas beyond `phase_a_output.gate`.

## Why

Until now Phase A returned `gate.render` as a Markdown blob and the main session emitted it verbatim. The user replied with free text (`"1=a 2=b"` or natural language). Two costs:

1. **Parsing fragility.** The main session had to interpret arbitrary text. `"1=a let me check first"` was indistinguishable from a material-change rebranch versus a simple pick. Heuristics were nowhere defined; it was per-call vibes.
2. **UX.** A multi-question gate was a wall of text with `[a]` / `[b]` markers. Picking one option among four meant typing `2=b`. The harness has a structured picker (`AskUserQuestion`) — using prose was leaving capability on the table.

The `AskUserQuestion` tool replaces both: structured options become a click, free-form via "Other"+notes is explicit (and we can apply heuristics to the notes only, not the whole gate reply).

## Schema changes

`schemas/phase-handoff.json` → `phase_a_output.gate`:

| field | before | after |
|---|---|---|
| `questions_count` max | `5` | `4` (matches `AskUserQuestion`'s 1–4 cap) |
| `gate_json_path` | — | required, abs path to `$WORKSPACE/gate.json` |
| `render` | primary | fallback only (renamed semantics in description) |

`gate.json` (Phase A's structured form, defined inline in the coordinator markdown — no JSON-schema file): added `header` field per question (≤12 chars, `user_language`).

## Main-session flow

1. Read `gate.gate_json_path`. Partition `binary`/`choice` from `open`.
2. Build one `AskUserQuestion` call from the structured questions:
   - `question = q.prompt`, `header = q.header`, `multiSelect: false`.
   - `options[] = [{label: opt.label, description: "+ <opt.pros>\n− <opt.cons>"}, …]`.
3. After resolution, follow up free-form on:
   - any picked option whose `pros`/`label` mentions `paste`/`probe output` (deploy-state probe paste) — append `\n<paste>` to the answer.
   - each `open` question.
4. Map answers back to keys via `gate.json` (label → key). `"Other"` → free-form text from `annotations.notes`.

## Material-change heuristics

Triggered when *any* answer's free-form content matches:

- contains a `path/to/file` slash-bearing token,
- contains a `file:line` reference,
- contains the literal word `actually`,
- contains a four-or-more-digit line number adjacent to a file token,
- explicitly contradicts a brief fact.

Match → re-spawn Phase A with `resume_from` + `gate_answers`. Else → simple resolution: write `gate_answers.json`, proceed to Phase B.

Ambiguous → one short clarifier, do not guess.

## Fallback path

Text rendering of `gate.md` is kept and used when:

- `gate_json_path` is missing, unreadable, or schema-invalid.
- Every question is `type: open`.
- `render_too_long: true`.

In the fallback path, parsing is the legacy free-form `"1=a 2=b"`-style. Same material-change heuristics apply.

## Deploy-state edge case

The `deploy_targets_unverified` question's `[a]` option (probe + paste) requires user-supplied output. Picker alone cannot capture it. Main session detects "paste"/"probe output" in `opt.pros` and asks for the paste as a follow-up text line. Encoded as `answer: "a\n<paste>"`. Phase A's deploy-state handler splits on the first newline — non-empty paste → `ground_truth.deploy_probe.output`, empty/`"skip"` → demoted to `[b]` semantics.

## Files touched

- `schemas/phase-handoff.json` — `phase_a_output.gate` (cap 4, +`gate_json_path`).
- `meta-agents/sub-coordinator-phase-a.md` — `header` field, cap 4, `gate_json_path` in handoff, deploy-state answer-format clarification.
- `SKILL.md` — `Handle the handoff` + `Gate iteration` rewritten for the picker flow.

## What this is NOT

- Not a change to Phase B/C handoffs, expert prompts, or synthesizer.
- Not a new schema file for `gate.json` (still defined inline in Phase A coordinator). Could be promoted later if the structure grows.
- Not a removal of the text path — `gate.md` is still written and used as fallback.
