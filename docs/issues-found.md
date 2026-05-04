# Issues found during live runs

Live-run findings are now tracked as **GitHub issues**:
<https://github.com/uwilleer/preflight/issues>

This file is a redirect-stub kept for historical link continuity. Original
2026-04-20 Milestone 2 smoke-run notes are preserved in git history at commit
`b665bce` (and the eight commits around it).

## Why the move

- Per-finding lifecycle (open / triaged / fixed / verified) is what GitHub issues
  are for; a flat markdown file conflated all four states.
- `field report` issues from real `/preflight` runs (e.g. issue #23) bring
  reproducible workspaces and cross-references to the offending lines in
  meta-agent prompts — both work better against issues than against an
  append-only file.
- Schema/docs drift detection (issue #10) and architecture overview (#11)
  belong in the same surface as the rest of the work.

## How to log a new finding

1. Open a new issue at the repo above. Title in the form
   `<area>: <one-line symptom>` (e.g. `phase-b: synthesizer returns empty
   panel array under <condition>`).
2. Body: paste the workspace path (or its `_index.json` if you can), the
   `_index.json.dispatch[]` block, and the smallest reproducer you have.
3. Label `field-report` if it came from a real `/preflight` run on a
   user-supplied artifact (vs. an eval fixture).
