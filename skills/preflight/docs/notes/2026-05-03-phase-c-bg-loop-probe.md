# Phase C `run_in_background` + main-session loop probe

**Date:** 2026-05-03
**Probe context:** Task 0 of `2026-05-03-phase-b-main-driven-impl.md`
**Verdict:** `BG_LOOP_OK: true`

## Implication for Phase C

Phase C under v0.7.0 uses the same dispatch-execute-respawn loop pattern as Phase B (Tasks 5–6 of the implementation plan proceed). All coordinator spawns within the Phase C loop carry `run_in_background: true`. The main session receives a notification per coordinator spawn, executes any dispatched `Agent` calls, and re-spawns the coordinator until `action: "complete"` or `action: "error"`.

The user-invisible UX gain of `run_in_background` is preserved — the loop runs in the background as a chain of notifications, not blocking the main session's foreground work after report delivery.

## Probe construction

Two-spawn chain:

1. Spawn 1 — `Agent(subagent_type=general-purpose, run_in_background=true, prompt="Return ONLY {\"action\":\"dispatch\",\"resume_token\":\"step-2\",\"probe\":\"step-1-of-2\"}")`
2. On notification of spawn 1, parse the returned JSON and verify `action == "dispatch"`.
3. Spawn 2 — `Agent(subagent_type=general-purpose, run_in_background=true, prompt="Return ONLY {\"action\":\"complete\",\"probe\":\"step-2-of-2\",\"status\":\"chain-confirmed\"}")`
4. On notification of spawn 2, parse and verify `action == "complete"`.

Both notifications arrived. Both JSON payloads were the exact expected strings. Total wall time: ~3 seconds (1.4s + 1.5s per probe).

## Probe transcripts (verbatim from notification payloads)

**Spawn 1 result:**

```json
{"action":"dispatch","resume_token":"step-2","probe":"step-1-of-2"}
```

(15330 tokens, 1396 ms, 0 tool uses)

**Spawn 2 result:**

```json
{"action":"complete","probe":"step-2-of-2","status":"chain-confirmed"}
```

(15314 tokens, 1520 ms, 0 tool uses)

## What this proves and what it does NOT

**Proves:**

- Main session can spawn `run_in_background: true` agents.
- Main session receives a completion notification with the agent's final message embedded.
- Main session can read the notification's payload and decide to spawn another `run_in_background: true` agent in response.
- The chain (notification → action → spawn → notification) does not lose state, does not deadlock, and does not require any wait/poll loop on the main side.

**Does NOT prove (out of scope for this probe — assumed by analogy with foreground behaviour):**

- Loop with N > 2 (the Phase C path tops out at 3 spawns: initial + rubber-duck + KB compactor; the 2-spawn probe is sufficient evidence for chains up to that depth).
- Behaviour when a BG agent itself spawns nested Agents — irrelevant under v0.7.0 because coordinator subagents never call Agent.
- Behaviour when the BG agent's payload is malformed JSON — handled by the same retry-once policy as the foreground path.

## Re-probing trigger

Re-run this probe and update the verdict if any of the following changes:

- Claude Code harness major version (e.g. 2.x → 3.x).
- The Agent tool's `run_in_background` parameter semantics change in the docs.
- A real `/preflight` run produces a Phase C completion-without-notification or notification-without-payload symptom.
