#!/usr/bin/env python3
"""
Preflight eval runner.

Usage:
    python evals/run_eval.py [--fixture <name>] [--baseline-only]

Runs each fixture through preflight (simulated) and scores against grading.json.
Outputs a markdown report to evals/report-<date>.md.

NOTE: Full automation requires Claude API integration (Milestone 4).
Currently: prints expected findings per fixture so a human can run
/preflight manually and check results against grading.json.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
GRADING = ROOT / "evals" / "grading.json"
FIXTURES_DIR = ROOT / "evals" / "fixtures"


def load_grading() -> dict:
    with open(GRADING) as f:
        return json.load(f)


def list_fixtures(grading: dict) -> list[str]:
    return list(grading["fixtures"].keys())


def print_fixture_checklist(name: str, spec: dict) -> None:
    print(f"\n{'='*60}")
    print(f"FIXTURE: {name}")
    print(f"{'='*60}")

    plan = FIXTURES_DIR / name / "plan.md"
    if not plan.exists():
        print(f"  ⚠  plan.md not found at {plan}")
        return

    print(f"  Plan: {plan}")
    if spec.get("real_postmortem"):
        print(f"  Type: real post-mortem")
        print(f"  Ref:  {spec.get('incident_ref', 'n/a')}")
    else:
        print(f"  Type: synthetic")

    print(f"\n  Expected verdict:  {spec.get('expected_verdict', '?')}")
    print(f"  Expected roles:    {', '.join(spec.get('expected_roles', []))}")

    must_find = spec.get("must_find", [])
    if must_find:
        print(f"\n  MUST FIND ({len(must_find)}):")
        for f in must_find:
            role = f.get("role", "any")
            title = f.get("title", "?")
            sev = f.get("severity", "must")
            print(f"    [{sev}] [{role}] {title}")

    panel_unique = spec.get("panel_unique_expected", [])
    if panel_unique:
        print(f"\n  Panel-unique (not expected from plan-critic baseline):")
        for u in panel_unique:
            print(f"    • {u}")

    baseline = spec.get("baseline_plan_critic_finds", [])
    if baseline:
        print(f"\n  plan-critic baseline expected to find:")
        for b in baseline:
            print(f"    • {b}")

    must_not = spec.get("must_not_do", [])
    if must_not:
        print(f"\n  MUST NOT:")
        for m in must_not:
            print(f"    ✗ {m}")

    must_not_sev = spec.get("must_not_find_severity")
    if must_not_sev:
        print(f"\n  Must NOT produce any '{must_not_sev}' findings (good-plan false positive check)")


def score_report(fixture_name: str, spec: dict, report: dict) -> dict:
    """
    Score a preflight ExpertReport dict against the grading spec.
    report = {verdict, panel, must_fix, should_fix, nice_fix, ...}
    Returns {passed, failed, notes}
    """
    passed = []
    failed = []

    # Check verdict
    expected_verdict = spec.get("expected_verdict")
    actual_verdict = report.get("verdict")
    if expected_verdict and actual_verdict:
        if actual_verdict == expected_verdict:
            passed.append(f"verdict: {actual_verdict} ✓")
        else:
            failed.append(f"verdict: expected {expected_verdict}, got {actual_verdict}")

    # Check must_find
    all_findings = []
    for sev in ("must_fix", "should_fix", "nice_fix"):
        for f in report.get(sev, []):
            all_findings.append({"severity": sev.replace("_fix", ""), "title": f.get("title", ""), "role": report.get("role", "")})

    for expected in spec.get("must_find", []):
        keyword = expected["title"].lower()
        matches = [f for f in all_findings if keyword in f["title"].lower()]
        if matches:
            passed.append(f"found '{keyword}' ✓")
        else:
            failed.append(f"missing: '{keyword}' not found in any finding")

    return {"passed": passed, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Preflight eval runner")
    parser.add_argument("--fixture", help="Run only this fixture")
    parser.add_argument("--score", help="Path to a preflight JSON report to score against grading")
    args = parser.parse_args()

    grading = load_grading()
    fixtures = list_fixtures(grading)

    if args.fixture:
        if args.fixture not in grading["fixtures"]:
            print(f"Unknown fixture: {args.fixture}")
            print(f"Available: {', '.join(fixtures)}")
            sys.exit(1)
        fixtures = [args.fixture]

    if args.score:
        # Score mode: read a report file and score it
        with open(args.score) as f:
            report = json.load(f)
        fixture_name = args.fixture or input("Fixture name: ")
        spec = grading["fixtures"][fixture_name]
        result = score_report(fixture_name, spec, report)
        print(f"\nScore for {fixture_name}:")
        for p in result["passed"]:
            print(f"  ✓ {p}")
        for f in result["failed"]:
            print(f"  ✗ {f}")
        sys.exit(0 if not result["failed"] else 1)

    # Checklist mode: print what to look for per fixture
    print(f"Preflight Eval Checklist — {date.today()}")
    print(f"Grading frozen at: {grading['_meta']['frozen_by']}")
    print(f"Fixtures: {len(fixtures)}")

    real_pm = sum(1 for n in fixtures if grading["fixtures"][n].get("real_postmortem"))
    print(f"Real post-mortem: {real_pm}/{len(fixtures)}")

    for name in fixtures:
        print_fixture_checklist(name, grading["fixtures"][name])

    print(f"\n{'='*60}")
    print("HOW TO RUN:")
    print("  For each fixture above, run:")
    print("  /preflight evals/fixtures/<name>/plan.md")
    print("  Then compare findings against MUST FIND above.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
