#!/usr/bin/env -S uv run --quiet --with jsonschema python3
"""Validate skills/preflight/schemas/_examples/*.json against schemas/phase-handoff.json.

Used by `make test-handoff`. Exits non-zero if any positive case fails OR any
negative case unexpectedly passes — both are schema regressions.

Positive cases live as files in _examples/. Negative cases are inline below
(tiny payloads designed to violate one specific constraint each).
"""
import json
import sys
from pathlib import Path
from jsonschema import Draft7Validator, RefResolver

SCHEMA_PATH = Path("skills/preflight/schemas/phase-handoff.json")
VERIFIER_SCHEMA_PATH = Path("skills/preflight/schemas/verifier-result.json")
EXAMPLES_DIR = Path("skills/preflight/schemas/_examples")

POSITIVE_CASES = [
    ("phase_b_complete.json", "phase_b_output"),
    ("phase_b_dispatch.json", "phase_b_output"),
    ("phase_b_error.json", "phase_b_output"),
    ("phase_c_complete.json", "phase_c_output"),
    ("phase_c_dispatch.json", "phase_c_output"),
]

# Standalone schemas (no $ref into phase-handoff) — validated separately.
STANDALONE_CASES = [
    ("verifier_result_verified_with_gt.json", VERIFIER_SCHEMA_PATH),
    ("verifier_result_unverified.json", VERIFIER_SCHEMA_PATH),
]

NEGATIVE_CASES = [
    (
        "phase_b complete missing report_path",
        "phase_b_output",
        {"workspace_path": "/x", "last_completed_step": 9, "action": "complete"},
    ),
    (
        "phase_b dispatch missing dispatch object",
        "phase_b_output",
        {"workspace_path": "/x", "last_completed_step": 6, "action": "dispatch"},
    ),
    (
        "phase_b error missing error_path",
        "phase_b_output",
        {"workspace_path": "/x", "last_completed_step": 7, "action": "error"},
    ),
    (
        "phase_b bad action enum",
        "phase_b_output",
        {"workspace_path": "/x", "last_completed_step": 9, "action": "wat"},
    ),
    (
        "phase_c complete missing kb_summary",
        "phase_c_output",
        {"workspace_path": "/x", "last_completed_step": 11, "action": "complete"},
    ),
    (
        "phase_b_dispatch.requests[].on_failure bad enum",
        "phase_b_dispatch",
        {
            "step": "7",
            "step_label": "x",
            "parallelism": "parallel",
            "requests": [
                {
                    "id": "r",
                    "subagent_type": "general-purpose",
                    "description": "x",
                    "prompt": "x",
                    "save_to": "/x",
                    "on_failure": "panic-and-die",
                }
            ],
            "resume_token": "post-7",
        },
    ),
]

# Standalone-schema negatives — validated against verifier-result.json directly.
STANDALONE_NEG_CASES = [
    (
        "verifier_result missing status",
        VERIFIER_SCHEMA_PATH,
        {"note": "x", "ground_truth_match": None},
    ),
    (
        "verifier_result bad status enum",
        VERIFIER_SCHEMA_PATH,
        {"status": "maybe", "note": "x", "ground_truth_match": None},
    ),
    (
        "verifier_result ground_truth_match missing kind",
        VERIFIER_SCHEMA_PATH,
        {"status": "verified", "note": "", "ground_truth_match": {"ref": "x"}},
    ),
    (
        "verifier_result ground_truth_match bad kind enum",
        VERIFIER_SCHEMA_PATH,
        {"status": "verified", "note": "", "ground_truth_match": {"kind": "wat", "ref": "x"}},
    ),
]


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    resolver = RefResolver.from_schema(schema)

    def make_validator(defn: str) -> Draft7Validator:
        return Draft7Validator(schema["definitions"][defn], resolver=resolver)

    failures = 0

    for fname, defn in POSITIVE_CASES:
        path = EXAMPLES_DIR / fname
        data = json.loads(path.read_text())
        errors = list(make_validator(defn).iter_errors(data))
        if errors:
            print(f"FAIL {fname} -> {defn}: {errors[0].message}")
            failures += 1
        else:
            print(f"OK   {fname} -> {defn}")

    # Standalone schemas (verifier-result.json etc.) — no $ref dependencies.
    for fname, schema_path in STANDALONE_CASES:
        path = EXAMPLES_DIR / fname
        data = json.loads(path.read_text())
        standalone_schema = json.loads(schema_path.read_text())
        errors = list(Draft7Validator(standalone_schema).iter_errors(data))
        if errors:
            print(f"FAIL {fname} -> {schema_path.name}: {errors[0].message}")
            failures += 1
        else:
            print(f"OK   {fname} -> {schema_path.name}")

    print()
    print("Negative cases (must all reject):")
    for label, defn, data in NEGATIVE_CASES:
        errors = list(make_validator(defn).iter_errors(data))
        if errors:
            print(f"OK   {label} -> rejected: {errors[0].message[:90]}")
        else:
            print(f"FAIL {label} -> unexpectedly passed validation")
            failures += 1

    for label, schema_path, data in STANDALONE_NEG_CASES:
        standalone_schema = json.loads(schema_path.read_text())
        errors = list(Draft7Validator(standalone_schema).iter_errors(data))
        if errors:
            print(f"OK   {label} -> rejected: {errors[0].message[:90]}")
        else:
            print(f"FAIL {label} -> unexpectedly passed validation")
            failures += 1

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nAll handoff examples validate; all negatives reject. OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
