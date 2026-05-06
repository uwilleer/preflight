# Pyramidal preflight — future direction note

**Status:** future direction — not implemented, not scheduled. Recorded for context.

**Date:** 2026-05-07

**Trigger:** user proposal during a session on parallelism / latency optimization. Analogy: deciding the colour of a brick is trivial; building a house requires planning architecture first, then design, then choosing the brick. Could `preflight` produce a "pyramid" of plan/decision-cards from architecture down to implementation detail (and, half-jokingly, even to indentation)?

## What the idea proposes

A single preflight invocation that auto-cascades through layers of detail on the same artefact:

1. **Top:** architecture / cross-cutting concerns / threat model.
2. **Middle:** subsystem design / module boundaries / API shape.
3. **Bottom:** implementation tasks / data-model details / step ordering.
4. **(Half-joke):** style / formatting / line-length.

Each layer is its own panel pass with experts narrowed to that layer's domain.

## Why we are NOT doing this as a single auto-cascading run

### 1. Cost explosion

Current `/preflight` run: ~50–150k tokens depending on artefact size and panel breadth (see `README.md` Numbers section). A 3-layer cascade ≈ 3× cost minimum (more if each layer fan-outs decomposed sub-artefacts). A 4-layer cascade down to style ≈ 5–10× — burning gold to mine copper at the bottom layer (see point 2). The user's stated principle "стоимость анализа приемлема, стоимость rework'а — нет" remains compatible with selective deep dives, not blanket pyramidal expansion.

### 2. Diminishing returns past the design layer

Multi-perspective LLM panels are maximally useful where right answers don't exist: architectural tradeoffs, security threat modelling, product / cost / SLO decisions. They are the **wrong tool** for layers below design:

- **Indentation, whitespace, line-length** → formatter (prettier / black / gofmt / rustfmt). Deterministic, instant, free.
- **Naming, unused imports, complexity heuristics** → linter (ruff / eslint / clippy). Deterministic, instant, near-free.
- **Type errors, contract mismatches** → typechecker. Deterministic, instant, near-free.
- **Behavioural correctness** → tests. Deterministic given a test, instant, cheap.

A Sonnet/Opus panel rendering an opinion on indentation would be (a) worse than the formatter, (b) ~1000× more expensive, (c) not even reproducible across runs. This is the load-bearing rejection: the bottom of the pyramid is **not panel territory**, it is **mechanical-tool territory**.

### 3. Responsibility conflict with sibling skills

`preflight` is specialised for **pre-write design review** — its `description` (default-gate framing as of `910170c`) explicitly says "BEFORE any code is written". The bottom layers of the pyramid overlap with skills that already exist:

- `requesting-code-review`, `code-review` — post-write code review.
- `security-review` — security audit on code, not plans.
- Linters / formatters / typecheckers — owned by the language toolchain.

Pyramidal preflight that descends to these layers is empire-building — same tool, multiple jobs, blurred semantics. Separation of concerns is a feature.

### 4. Single-run coupling kills user control over budget

A single auto-cascading invocation removes the user's ability to stop after layer 1 if the architecture is sound and only the design decomposition is interesting. The current /preflight gives the user one explicit decision per invocation; pyramidal-as-one-run replaces that with N implicit decisions hidden inside the run.

## Forms of the idea that ARE worth considering later

### Form A: `depth=` parameter on `/preflight` invocation

`/preflight depth=brief` (current default), `/preflight depth=detailed`, `/preflight depth=cascade`.

- `brief` — current behaviour. Single panel pass over the full artefact.
- `detailed` — `brief` + automatic second-pass narrow panel on each MUST-FIX from the first pass. Each MUST-FIX gets a 1–2 expert mini-panel scoped to that specific concern. Cost ~2–3×.
- `cascade` — Phase A decomposes the artefact by section / feature / component into N sub-artefacts; runs N parallel mini-preflights, each producing its own report; the top-level report aggregates. Cost ~N×.

Key requirement: cost shown to the user up-front, opt-in per invocation. **Default never changes from `brief`.**

Prerequisite: timing instrumentation (this commit) tells us empirically what `2×` and `N×` actually cost in seconds and tokens for a representative artefact. Without that, "depth=detailed" is sold to the user with imaginary numbers.

### Form B: `preflight-cascade` sibling skill

A separate skill that:

1. Takes the output of a previous `/preflight` run (its `report.md` + `synth_result.json`).
2. Parses `decisions[]` and `must_fix[]`.
3. Surfaces each item to the user as: "this decision/must-fix could be reviewed in its own preflight — proceed?"
4. On confirmation, recursively invokes `/preflight` with the sub-question as a fresh artefact (claim-extraction → ground_truth → panel → report).

Human-in-the-loop, transparent budget, no surprise cascading. Lives outside `preflight`'s repo as a separate concern.

### Form C: artefact-internal hierarchy awareness

If the artefact ITSELF has a hierarchical structure (`# Architecture / ## Design / ### Tasks` or similar), Phase A's brief extraction can already detect this and pass per-section context to per-section experts. This is a smaller, in-scope improvement that doesn't require a multi-pass pipeline. Probably worth ~1 expert-prompt change in roles signalling "you focus on the design level only, ignore implementation tasks below".

## Out of scope, permanently

- **Auto-cascade to style / indentation / formatting / linting.** Wrong tool. Defer to formatter/linter/typechecker. Do not consume LLM tokens on this.
- **Mandatory pyramidal mode.** Removes user budget control. Default stays `brief`.
- **Recursive panel-of-panels without explicit user approval.** Runaway cost.

## Decision

**Defer.** Forms A and B are revisited after timing instrumentation produces real measurements. Form C is in scope as a small, optional improvement — track via GitHub issue if/when an artefact's hierarchy actually shows up unexploited.

This document exists so the idea isn't forgotten and so the decision (and its reasoning) survives across sessions. If a future contributor revisits "pyramidal preflight," they should read this first and then update it — don't relitigate from scratch.

## Cross-references

- `SKILL.md` — current `description` (default-gate, opt-in→default shift in commit `910170c`).
- `README.md` Numbers section — cost/token baseline (~50–150k per run).
- `docs/architecture.md` — three-phase pipeline.
- This commit — timing instrumentation, the prerequisite for evaluating `depth=` cost claims empirically.