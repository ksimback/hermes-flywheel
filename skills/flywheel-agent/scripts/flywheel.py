#!/usr/bin/env python3
"""
Flywheel one-command entrypoint.

Wraps the deterministic pipeline so a founder (or the agent, or CI) can run a
whole sprint with one command instead of eight, and can check their setup.

    flywheel.py run --demo                 # full ExampleAI demo, no keys needed
    flywheel.py run "Product: ... ICP: ..." # real sprint from founder context
    flywheel.py doctor                     # environment / readiness check

`run` orchestrates: intake -> launch -> backlinks -> leads -> creators ->
MPP -> trends -> sprint report -> validate. For a real (non-demo) run it uses
live research where it can (research.py with SERPER_API_KEY for backlinks and
trends; data/leads.csv for outbound) and cleanly SKIPS any stage whose input
isn't available, producing a partial sprint rather than failing -- the agent
can fill the gaps with --input and re-run. Nothing is ever silently faked.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from _common import anchor, artifact_is_stale, configure_stdout

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable

# Artifact files owned by each skippable stage (json first, then siblings).
_STAGE_ARTIFACTS = {
    "backlinks": ("backlink_opportunities.json", "backlink_opportunities.md"),
    "outbound": ("outbound_queue.json", "outbound_queue.md"),
    "creators": ("creator_campaign.json", "creator_campaign.md"),
    "trends": ("trend_content.json", "trend_content.md"),
}


def _clear_stale_skipped_artifacts(args, skipped):
    """A skipped stage must leave no stale artifact behind.

    A prior run in the same output dir (typically --demo) may have written a
    skipped stage's files; without cleanup those leftovers would sit next to
    real output and get consumed downstream. Only files that are provably
    stale for the current profile (demo-mode in a real run, or a different
    product's stamp) are removed - a re-run of the SAME product keeps its own
    artifacts, so continuing a sprint stays non-destructive.
    """
    try:
        with anchor(args.profile).open(encoding="utf-8") as f:
            profile = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    for entry in skipped:
        stage = entry.split(" ", 1)[0]
        filenames = _STAGE_ARTIFACTS.get(stage)
        if not filenames:
            continue
        json_path = anchor(str(Path(args.output_dir) / filenames[0]))
        try:
            with json_path.open(encoding="utf-8") as f:
                artifact = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        reason = artifact_is_stale(artifact, profile)
        if not reason:
            continue
        for name in filenames:
            path = anchor(str(Path(args.output_dir) / name))
            if path.exists():
                path.unlink()
        print(f"🧹 Removed stale {filenames[0]} ({reason}); the {stage} section stays skipped until real input is supplied.")


def _run(script, *args):
    """Run a pipeline script; return its exit code (never raises)."""
    cmd = [PY, str(SCRIPTS / script), *args]
    return subprocess.run(cmd).returncode


def _has_key(name):
    val = os.environ.get(name, "").strip()
    return bool(val) and not val.startswith("replace_with")


def cmd_run(args):
    profile = args.profile
    out = ["--output-dir", args.output_dir]

    # 1. Intake
    if args.demo:
        rc = _run("flywheel_intake.py", "--demo", "--output", profile)
    elif args.context:
        rc = _run("flywheel_intake.py", args.context, "--output", profile)
    else:
        print("❌ Provide product context, or use --demo. Example:")
        print("   flywheel.py run \"Product: Acme (https://acme.co) ICP: founders Budget: $200 Focus: launch\"")
        return 2
    if rc != 0:
        print("❌ Intake failed; stopping.")
        return rc

    prof = ["--profile", profile]
    demo_flag = ["--demo"] if args.demo else []

    # A stage returning EXIT_MISSING_INPUT (2) was intentionally skipped for
    # lack of input -> partial sprint. Any OTHER non-zero code is a real crash
    # and must fail the run (never excused by --partial).
    skipped = []
    crashed = []

    def stage(label, script, *extra):
        rc = _run(script, *prof, *out, *extra)
        if rc not in (0, 2):
            crashed.append(f"{label} (exit {rc})")
        return rc

    # 2. Launch plan (always profile-derived)
    stage("launch", "launch_plan.py")

    # 3. Research-backed stages: demo fixtures, live SERPER, or skip.
    _stage_research(args, "backlink_hunter.py", "backlinks", prof, out, skipped, crashed)
    _stage_leads(args, prof, out, skipped, crashed)
    _stage_research(args, "trend_scan.py", "trends", prof, out, skipped, crashed)

    # 4. Creators, then stale-leftover cleanup, then MPP (which reads the
    #    sibling artifacts and must never see another run's files).
    if args.demo:
        stage("creators", "creator_campaign.py", "--demo")
    else:
        if stage("creators", "creator_campaign.py") == 2:
            skipped.append("creators (needs --input creator research)")
    _clear_stale_skipped_artifacts(args, skipped)
    stage("mpp", "mpp_spend_planner.py")

    # 5. Compile + validate. A partial run (stages skipped for lack of input)
    #    validates in --partial mode so missing artifacts are warnings, not a
    #    failure -- but safety/approval/secret checks still hard-fail.
    sprint_args = prof + out + (["--new-sprint"] if args.new_sprint else [])
    if _run("sprint_report.py", *sprint_args) != 0:
        crashed.append("sprint_report")
    validate_args = prof + out + (["--partial"] if skipped else [])
    rc = _run("validate_outputs.py", *validate_args)

    if crashed:
        print("\n❌ A pipeline stage failed (not a skip): " + "; ".join(crashed))
        print("   This is a real error, not a partial sprint. See the stage output above.")
        return 1
    if skipped:
        print("\nℹ️  Partial sprint. Skipped (no input available): " + "; ".join(skipped))
        print("   Supply agent research via --input to each script, or set SERPER_API_KEY, then re-run.")
    print(f"\n✓ Sprint compiled to {args.output_dir}/weekly_flywheel_sprint.md")
    return 0 if rc == 0 else rc


def _stage_research(args, script, target, prof, out, skipped, crashed):
    """Run a research-backed stage: demo fixture, live SERPER, or skip."""
    if args.demo:
        if _run(script, *prof, *out, "--demo") != 0:
            crashed.append(f"{target} (demo, crashed)")
        return
    if _has_key("SERPER_API_KEY"):
        research_out = str(Path(args.output_dir) / f"research_{target}.json")
        rc = _run("research.py", *prof, "--for", target, "--output", research_out)
        if rc == 0:
            if _run(script, *prof, *out, "--input", research_out) != 0:
                crashed.append(f"{target} (crashed on live research)")
            return
        # research.py exit 2 = no/invalid key -> skip; other codes = a real
        # research failure worth surfacing, but still a partial (no artifact).
    skipped.append(f"{target} (set SERPER_API_KEY or pass --input to {script})")


def _stage_leads(args, prof, out, skipped, crashed):
    if args.demo:
        if _run("lead_scorer.py", *prof, *out, "--demo") != 0:
            crashed.append("outbound (demo, crashed)")
        return
    # Use an explicit --leads-csv if given, else lead_scorer auto-detects
    # data/leads.csv. Exit 2 means no lead source is available.
    extra = ["--leads-csv", args.leads_csv] if getattr(args, "leads_csv", None) else []
    rc = _run("lead_scorer.py", *prof, *out, *extra)
    if rc == 2:
        skipped.append("outbound (pass --leads-csv <file>, add data/leads.csv, or --input leads research)")
    elif rc != 0:
        crashed.append(f"outbound (exit {rc})")


def cmd_doctor(args):
    print("🩺 Flywheel doctor\n")
    ok = True

    # Python
    v = sys.version_info
    py_ok = (v.major, v.minor) >= (3, 8)
    print(f"  [{'✓' if py_ok else '✗'}] Python {v.major}.{v.minor} (need >= 3.8)")
    ok = ok and py_ok

    # Scripts present
    required = [
        "flywheel_intake.py", "launch_plan.py", "backlink_hunter.py", "lead_scorer.py",
        "creator_campaign.py", "mpp_spend_planner.py", "trend_scan.py", "sprint_report.py",
        "validate_outputs.py", "sprint_ledger.py", "approvals.py", "research.py",
        "stripe_client.py", "_common.py",
    ]
    missing = [s for s in required if not (SCRIPTS / s).exists()]
    print(f"  [{'✓' if not missing else '✗'}] Pipeline scripts present"
          + (f" (missing: {', '.join(missing)})" if missing else ""))
    ok = ok and not missing

    # Optional capabilities
    serper = _has_key("SERPER_API_KEY")
    print(f"  [{'✓' if serper else '·'}] SERPER_API_KEY {'set — live headless research available' if serper else 'not set — use --input or --demo'}")

    stripe_val = os.environ.get("STRIPE_API_KEY", "").strip()
    if stripe_val and not stripe_val.startswith("replace_with"):
        if stripe_val.startswith("sk_test_"):
            print("  [✓] STRIPE_API_KEY is a test key — real test-mode MPP intents available")
        else:
            print("  [!] STRIPE_API_KEY is NOT a test key — it will be refused; MPP stays simulated")
    else:
        print("  [·] STRIPE_API_KEY not set — MPP stays simulated (no keys needed)")

    # Profile / state
    from _common import anchor  # local import so doctor works from any cwd
    prof = anchor("data/product_profile.json")
    print(f"  [{'✓' if prof.exists() else '·'}] Product profile {'exists' if prof.exists() else 'not yet created (run intake)'}")

    print("\n" + ("✓ Ready." if ok else "✗ Fix the ✗ items above before running."))
    return 0 if ok else 1


def main():
    configure_stdout()
    parser = argparse.ArgumentParser(description="Flywheel one-command entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a full sprint end to end.")
    p_run.add_argument("context", nargs="?", help="Founder product context (omit for --demo).")
    p_run.add_argument("--demo", action="store_true", help="Run the ExampleAI demo (no keys).")
    p_run.add_argument("--profile", default="data/product_profile.json")
    p_run.add_argument("--output-dir", default="demo/demo-output")
    p_run.add_argument("--leads-csv",
                       help="Path to your leads CSV for warm outbound "
                            "(columns: name,title,company,bio,source,url,engagement_context). "
                            "Defaults to auto-detecting data/leads.csv.")
    p_run.add_argument("--new-sprint", action="store_true",
                       help="Start a new sprint (archive the prior one) instead of continuing.")

    sub.add_parser("doctor", help="Check environment and readiness.")

    args = parser.parse_args()
    if args.command == "run":
        return cmd_run(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
