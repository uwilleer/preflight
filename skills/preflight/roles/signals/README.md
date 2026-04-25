# Signal-group checklists

Small domain-specific augmenters that the selector mixes into a role's KB when the brief contains matching keywords. Each YAML adds a checklist that experts of the augmented role consult in addition to their general role prompt.

## YAML schema

```yaml
group: <slug, e.g. "auth">
matchers:
  - <case-insensitive substring or /regex/ to detect in brief.md>
augments_roles:
  - <role name from roles/index.json>
checklist_intro: |
  <one paragraph the expert reads before the checklist items>
checklist:
  - id: <stable short id>
    title: <one-line action-first label>
    rationale: <one sentence — why this matters>
```

## Wiring (implemented in selector.md and sub-coordinator-phase-a.md)

1. selector scans `brief.md` for each YAML's matchers (case-insensitive substring; /regex/ if wrapped in slashes).
2. Matched groups → `signals[]` in selector output → written to `$WORKSPACE/signals.json`.
3. Phase A role-KB build: for each role in the panel, finds signals that augment it, appends checklist_intro + checklist items to `$WORKSPACE/role_kb/<role>.md`.
4. Experts read augmented KB transparently. No expert-prompt changes needed.

## Adding new signal groups

Create a new `roles/signals/<group>.yaml` following the schema above. Run `make build-index` to refresh `roles/index.json` with the new signal group entry (or add manually if make is unavailable).
