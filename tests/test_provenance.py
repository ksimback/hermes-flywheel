"""Provenance guard: another run's artifacts must never be presented as this
run's data.

The founding bug (found by a cold clone-and-follow test): run `flywheel.py run
--demo`, then run a REAL sprint for a different product into the same output
dir. The skipped stages left the demo's outbound leads, backlinks, and creator
spend requests on disk, and sprint_report/mpp_spend_planner compiled them into
the real report with "Demo Mode: False" - fabricated data presented as real,
the exact thing the README promises never happens.

Three layers now enforce provenance, and each is covered here:
- _common.artifact_is_stale is the single staleness rule (unit tests).
- sprint_report and mpp_spend_planner refuse stale artifacts (integration).
- flywheel.py removes stale files for stages it skipped (integration).
- validate_outputs hard-fails a real report containing demo artifacts, and
  --partial must NOT downgrade that (it is a plain string, not Completeness).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"

sys.path.insert(0, str(SCRIPTS))
from _common import artifact_is_stale  # noqa: E402
import validate_outputs  # noqa: E402

FIXTURE_MARKERS = ["CartPilot", "Aisha Morgan", "StoreGrowthDemo", "ExampleAI"]


def run(cmd, check=True):
    result = subprocess.run(
        [sys.executable, *cmd], capture_output=True, text=True, cwd=ROOT,
        encoding="utf-8", errors="replace",
    )
    if check:
        assert result.returncode == 0, f"{cmd} failed:\n{result.stdout}\n{result.stderr}"
    return result


# ---------------------------------------------------------------------------
# Unit: the staleness rule
# ---------------------------------------------------------------------------

def test_demo_artifact_is_stale_for_real_profile():
    reason = artifact_is_stale({"demo_mode": True}, {"demo_mode": False})
    assert reason and "demo" in reason


def test_demo_artifact_is_fine_for_demo_profile():
    assert artifact_is_stale({"demo_mode": True}, {"demo_mode": True}) is None


def test_other_products_artifact_is_stale():
    reason = artifact_is_stale(
        {"demo_mode": False, "product_name": "OldCo"},
        {"demo_mode": False, "product_name": "NewCo"},
    )
    assert reason and "OldCo" in reason


def test_same_product_artifact_is_fine():
    artifact = {"demo_mode": False, "product_name": "MyCo"}
    assert artifact_is_stale(artifact, {"demo_mode": False, "product_name": "MyCo"}) is None


def test_unstamped_artifact_is_not_judged_by_product():
    # Legacy artifacts without a product stamp can't be product-checked;
    # only the demo flag applies.
    assert artifact_is_stale({"demo_mode": False}, {"product_name": "MyCo"}) is None


def test_empty_or_non_dict_artifacts_are_ignored():
    assert artifact_is_stale(None, {}) is None
    assert artifact_is_stale({}, {}) is None
    assert artifact_is_stale("not a dict", {}) is None


# ---------------------------------------------------------------------------
# Integration: demo run then real run in the same output dir
# ---------------------------------------------------------------------------

def test_real_run_after_demo_contains_no_fixture_data(tmp_path):
    out = tmp_path / "out"
    profile = tmp_path / "profile.json"
    flywheel = str(SCRIPTS / "flywheel.py")

    run([flywheel, "run", "--demo",
         "--output-dir", str(out), "--profile", str(profile)])

    result = run([flywheel, "run",
                  "Product: FounderPilot (https://founderpilot.example) "
                  "ICP: technical founders Competitors: rival.example "
                  "Budget: $500 Focus: launch",
                  "--output-dir", str(out), "--profile", str(profile),
                  "--new-sprint"])

    report_md = (out / "weekly_flywheel_sprint.md").read_text(encoding="utf-8")
    for marker in FIXTURE_MARKERS:
        assert marker not in report_md, (
            f"fixture marker {marker!r} leaked into a real sprint report"
        )

    # The stale demo files for skipped stages must be gone, not lingering
    # next to real output.
    for leftover in ["outbound_queue.json", "backlink_opportunities.json",
                     "creator_campaign.json", "trend_content.json"]:
        assert not (out / leftover).exists(), f"stale {leftover} left behind"

    # And the run said so, honestly.
    assert "Removed stale" in result.stdout
    assert "Partial sprint" in result.stdout


def test_mpp_planner_ignores_stale_demo_creator_requests(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({
        "product_name": "RealCo",
        "demo_mode": False,
        "budget": {"weekly_usd": 500, "max_single_spend_usd": 100},
    }), encoding="utf-8")

    # A stale demo creator artifact sitting in the output dir.
    (out / "creator_campaign.json").write_text(json.dumps({
        "demo_mode": True,
        "product_name": "ExampleAI",
        "spend_requests": [{
            "creator": "StoreGrowthDemo", "amount_usd": 100,
            "expected_outcome": "demo outcome",
        }],
    }), encoding="utf-8")

    result = run([str(SCRIPTS / "mpp_spend_planner.py"),
                  "--profile", str(profile_path), "--output-dir", str(out)])
    assert "Ignoring stale creator_campaign.json" in result.stdout

    cards = json.loads((out / "mpp_spend_cards.json").read_text(encoding="utf-8"))
    card_names = json.dumps(cards["spend_cards"])
    assert "StoreGrowthDemo" not in card_names


# ---------------------------------------------------------------------------
# Validator: the regression guard is a hard failure, not --partial-downgradable
# ---------------------------------------------------------------------------

def test_validator_rejects_demo_artifact_in_real_report(tmp_path):
    report = tmp_path / "weekly_flywheel_sprint.json"
    report.write_text(json.dumps({
        "sprint_summary": {
            "demo_mode": False,
            "total_actions": 5,
            "approval_gates": {"outbound_messages": 1, "content_posts": 0},
            "budget_analysis": {"weekly_budget": 500},
        },
        "next_week_plan": {"focus_areas": ["launch"]},
        "detailed_data": {
            "outbound_queue": {"demo_mode": True, "leads": []},
        },
    }), encoding="utf-8")

    issues = validate_outputs.validate_sprint_report(report)
    provenance_issues = [i for i in issues if "demo-mode artifact" in str(i)]
    assert provenance_issues, "validator must flag demo artifacts in a real report"
    # Plain strings are never downgraded by --partial (only Completeness is).
    for issue in provenance_issues:
        assert type(issue) is str


def test_validator_accepts_demo_artifacts_in_demo_report(tmp_path):
    report = tmp_path / "weekly_flywheel_sprint.json"
    report.write_text(json.dumps({
        "sprint_summary": {
            "demo_mode": True,
            "total_actions": 5,
            "approval_gates": {"outbound_messages": 1, "content_posts": 0},
            "budget_analysis": {"weekly_budget": 2000},
        },
        "next_week_plan": {"focus_areas": ["launch"]},
        "detailed_data": {
            "outbound_queue": {"demo_mode": True, "leads": []},
        },
    }), encoding="utf-8")

    issues = validate_outputs.validate_sprint_report(report)
    assert not [i for i in issues if "demo-mode artifact" in str(i)]
