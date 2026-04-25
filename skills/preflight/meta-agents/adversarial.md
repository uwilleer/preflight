# Adversarial mode — prompt fragment

This prompt fragment is APPENDED to an expert role's prompt during Phase B step 7.5 (the adversarial round), after your first-pass report has been submitted and after all experts' reports are collected. You now see your own first-pass report plus the high-severity findings of every other panel member.

## What you have

```json
{
  "your_prior_report": { "...your step-7 ExpertReport JSON..." },
  "peer_findings": [
    {
      "id": "<stable id, e.g. 'security:must:0'>",
      "title": "...",
      "evidence": "...",
      "replacement": "...",
      "tier": "must_fix | should_fix",
      "reporter_role": "security"
    }
  ]
}
```

`peer_findings` excludes your own findings. It includes only `must_fix` and `should_fix` from other experts (max 8 entries — largest panels are pre-trimmed by the coordinator).

## Your task

For **each** peer finding, pick exactly one action:

- **`concede`** — you agree it is a real issue in scope of this artifact. The synthesizer treats this as a cross-confirmation (raises confidence, may upgrade tier). No evidence required.
- **`challenge`** — you have specific reason to believe the finding is wrong, irrelevant in this context, or contradicts your domain knowledge. You MUST cite: a file/line you grepped, a brief excerpt, or a named domain rule (e.g. "RFC 7231 §6.5.1"). Vague disagreement ("I don't think this matters") is NOT a challenge — use `pass` instead.
- **`refine`** — the finding points at a real issue but the framing or replacement is wrong. You provide a corrected replacement. Must include `corrected_replacement`.
- **`pass`** — outside your domain, no opinion. Synthesizer ignores.

## Output

Append `adversarial_responses` to your top-level ExpertReport JSON:

```json
"adversarial_responses": [
  {
    "target_finding_id": "security:must:0",
    "action": "concede" | "challenge" | "refine" | "pass",
    "evidence": "<required for challenge and refine; empty string for concede/pass>",
    "corrected_replacement": "<required for refine; empty string otherwise>"
  }
]
```

One entry per peer finding. Preserve the order. No omissions.

## Anti-patterns

- **Conceding everything to be agreeable.** If a peer finding is wrong, challenge it. Sycophancy in adversarial mode defeats the entire purpose.
- **Challenging without evidence.** "I don't think so" is a `pass`, not a `challenge`.
- **Adding new findings.** Adversarial mode is response-only. New findings in `adversarial_responses` will be ignored by the synthesizer.
- **Changing your own prior findings.** Your first-pass report is frozen. You only respond to peers.
