"""Tests for the Phase 3 "flywheel core": the approval state machine
(sprint_ledger + approvals.py) and the cross-sprint learning loop, plus the
validate_outputs approval-gate enforcement.

Two layers of coverage:

- Pure state-machine / learning-loop unit tests import sprint_ledger directly
  and drive it with small hand-built data. No subprocess, so these are fast and
  precise about the transition guards.
- Integration tests seed a full demo sprint into an isolated tmp dir (the same
  pipeline the committed demo uses) and drive the real approvals.py CLI, then
  assert the resulting sprint_state.json.

Everything is isolated to tmp_path: sprint state lives beside the --profile
file (ledger.state_dir_for), so pointing --profile at a temp dir keeps the
committed repo tree untouched.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"

# Direct-import the deterministic ledger logic (mirrors test_units.py).
sys.path.insert(0, str(SCRIPTS))
import sprint_ledger as ledger  # noqa: E402

DEMO_ITEM_COUNT = 38  # launch 8, backlinks 10, outbound 10, content 5, creator 1, mpp_spend 4

DOWNSTREAM = [
    "launch_plan.py",
    "backlink_hunter.py",
    "lead_scorer.py",
    "creator_campaign.py",
    "mpp_spend_planner.py",
    "trend_scan.py",
    "sprint_report.py",
]


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def run(cmd, check=True):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def approvals(profile, *args, check=False):
    """Invoke approvals.py against a profile's sprint state."""
    return run(
        [sys.executable, str(SCRIPTS / "approvals.py"),
         "--profile", str(profile), *args],
        check=check,
    )


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def load_state(tmp_dir):
    return load_json(Path(tmp_dir) / ledger.STATE_FILENAME)


def status_counts(state):
    counts = {}
    for it in state["items"]:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return counts


@pytest.fixture
def sprint(tmp_path):
    """Seed one full demo sprint into an isolated tmp dir.

    Returns {"dir", "profile", "out"}. The sprint_state.json and
    sprint_history.jsonl live in `dir` (beside the profile), never in the repo.
    Function-scoped so each mutation test gets a fresh, independent sprint.
    """
    profile = tmp_path / "product_profile.json"
    out = tmp_path / "out"
    run([sys.executable, str(SCRIPTS / "flywheel_intake.py"),
         "--demo", "--output", str(profile)])
    for script in DOWNSTREAM:
        run([sys.executable, str(SCRIPTS / script),
             "--profile", str(profile), "--output-dir", str(out)])
    return {"dir": tmp_path, "profile": profile, "out": out}


# ---------------------------------------------------------------------------
# Hand-built data for the pure ledger tests (no subprocess)
# ---------------------------------------------------------------------------

def small_all_data():
    """Minimal artifact bundle exercising every approvable section."""
    return {
        "launch_plan": {"launch_channels": [
            {"channel": "producthunt", "name": "Product Hunt"},
            {"channel": "hn", "name": "Hacker News"},
        ]},
        "backlink_opportunities": {"opportunities": [
            {"id": "opp_1", "title": "Dev directory"},
        ]},
        "outbound_queue": {"leads": [
            {"name": "Ada", "company": "Acme"},
        ]},
        "trend_content": {"content_drafts": [
            {"trend": "AI agents", "platform": "twitter"},
        ]},
        "creator_campaign": {"spend_requests": [
            {"id": "spend_1", "creator": "Grace", "amount_usd": 50},
        ]},
        "mpp_spend_cards": {"spend_cards": [
            {"id": "mpp_1", "resource_name": "Paid data", "amount_usd": 30},
        ]},
    }


def seed_small(tmp_dir, run_id="run-1", new_sprint=False):
    return ledger.seed_sprint(tmp_dir, run_id, "SmallCo", small_all_data(),
                              generated_at="2026-07-01T00:00:00", new_sprint=new_sprint)


# ---------------------------------------------------------------------------
# Ledger unit tests: item registry + state machine guards
# ---------------------------------------------------------------------------

def test_build_item_registry_covers_all_sections():
    items = ledger.build_item_registry(small_all_data())
    sections = {it["section"] for it in items}
    assert sections == set(ledger.APPROVABLE_SECTIONS)
    assert len(items) == 7  # 2 launch channels + 1 each of the other 5 sections
    assert all(it["status"] == ledger.PENDING for it in items)
    # Amounts flow through for spend-bearing sections.
    creator = next(it for it in items if it["section"] == "creator")
    assert creator["amount_usd"] == 50


def test_approve_and_execute_are_locked_in_draft(tmp_path):
    state = seed_small(tmp_path)
    item_id = state["items"][0]["id"]

    ok, msg = ledger.set_item_status(state, item_id, ledger.APPROVED)
    assert ok is False
    assert "finalize" in msg.lower()
    assert state["items"][0]["status"] == ledger.PENDING

    ok, _ = ledger.set_item_status(state, item_id, ledger.EXECUTED)
    assert ok is False


def test_finalize_is_idempotent(tmp_path):
    state = seed_small(tmp_path)
    ok, msg = ledger.finalize(state)
    assert ok is True
    assert state["sprint_state"] == ledger.SPRINT_FINALIZED

    ok, msg = ledger.finalize(state)
    assert ok is False
    assert "already finalized" in msg.lower()


def test_item_transition_lifecycle(tmp_path):
    state = seed_small(tmp_path)
    ledger.finalize(state)
    a, b = state["items"][0]["id"], state["items"][1]["id"]

    assert ledger.set_item_status(state, a, ledger.APPROVED)[0] is True
    # Can't approve something already approved.
    assert ledger.set_item_status(state, a, ledger.APPROVED)[0] is False
    # Approved -> executed works; pending -> executed does not.
    assert ledger.set_item_status(state, a, ledger.EXECUTED)[0] is True
    assert ledger.set_item_status(state, b, ledger.EXECUTED)[0] is False
    # Rejecting an executed item is refused; a pending one is fine.
    assert ledger.set_item_status(state, a, ledger.REJECTED)[0] is False
    assert ledger.set_item_status(state, b, ledger.REJECTED)[0] is True


def test_apply_bulk_scopes_to_a_section(tmp_path):
    state = seed_small(tmp_path)
    ledger.finalize(state)
    changed, _ = ledger.apply_bulk(state, ledger.APPROVED, section="launch")
    assert changed == 2  # both launch channels
    approved = [it for it in state["items"] if it["status"] == ledger.APPROVED]
    assert {it["section"] for it in approved} == {"launch"}


def test_render_status_runs(tmp_path):
    state = seed_small(tmp_path)
    text = ledger.render_status(state)
    assert "SmallCo" in text
    assert "LOCKED" in text  # draft => execution locked
    assert ledger.render_status(None).startswith("No sprint state")


# ---------------------------------------------------------------------------
# Ledger unit tests: seeding + history archival policy
# ---------------------------------------------------------------------------

def test_untouched_draft_is_discarded_not_archived(tmp_path):
    seed_small(tmp_path, run_id="run-1")
    # Re-seed with a different run; the prior all-pending draft was never
    # engaged, so it must be discarded rather than written to history.
    seed_small(tmp_path, run_id="run-2")
    assert ledger.read_history(tmp_path) == []


def test_engaged_sprint_is_archived_on_new_sprint(tmp_path):
    state = seed_small(tmp_path, run_id="run-1")
    ledger.finalize(state)
    creator = next(it for it in state["items"] if it["section"] == "creator")
    ledger.set_item_status(state, creator["id"], ledger.APPROVED)
    ledger.save_state(tmp_path, state)

    # Explicitly starting a new sprint archives the engaged prior one.
    seed_small(tmp_path, run_id="run-2", new_sprint=True)
    history = ledger.read_history(tmp_path)
    assert len(history) == 1
    rec = history[0]
    assert rec["run_id"] == "run-1"
    assert rec["final_sprint_state"] == ledger.SPRINT_FINALIZED
    assert rec["approved_by_section"].get("creator") == 1
    assert rec["total_approved_spend_usd"] == 50


def test_recompile_same_product_preserves_approvals_and_does_not_archive(tmp_path):
    """The Finding-4 guarantee: re-running the pipeline mid-review (a fresh
    run_id, same product, no --new-sprint) must NOT wipe approvals or archive."""
    state = seed_small(tmp_path, run_id="run-1")
    ledger.finalize(state)
    creator = next(it for it in state["items"] if it["section"] == "creator")
    ledger.set_item_status(state, creator["id"], ledger.APPROVED)
    ledger.save_state(tmp_path, state)

    # Re-compile with a DIFFERENT run_id (as sprint_report always mints) but
    # not a new sprint: decisions and finalized flag survive; nothing archived.
    reconciled = seed_small(tmp_path, run_id="run-2")
    assert reconciled["sprint_state"] == ledger.SPRINT_FINALIZED
    assert reconciled["run_id"] == "run-1"  # continues the original sprint
    kept = next(it for it in reconciled["items"] if it["id"] == creator["id"])
    assert kept["status"] == ledger.APPROVED
    assert ledger.read_history(tmp_path) == []


def test_reseed_same_run_id_preserves_approvals(tmp_path):
    state = seed_small(tmp_path, run_id="run-1")
    ledger.finalize(state)
    ledger.set_item_status(state, state["items"][0]["id"], ledger.APPROVED)
    ledger.save_state(tmp_path, state)

    # Same run_id => idempotent, keeps the finalized state and approvals.
    again = seed_small(tmp_path, run_id="run-1")
    assert again["sprint_state"] == ledger.SPRINT_FINALIZED
    assert again["items"][0]["status"] == ledger.APPROVED


# ---------------------------------------------------------------------------
# Ledger unit tests: the learning loop
# ---------------------------------------------------------------------------

def test_opportunity_scores_compute_per_section_rates():
    history = [{
        "approved_by_section": {"launch": 3, "outbound": 1},
        "rejected_by_section": {"launch": 1, "outbound": 3},
        "counts": {ledger.APPROVED: 4, ledger.REJECTED: 4, ledger.EXECUTED: 0},
    }]
    scores = ledger.opportunity_scores(history)
    assert scores["launch"]["approval_rate"] == 0.75
    assert scores["outbound"]["approval_rate"] == 0.25
    assert scores["launch"]["decided"] == 4


def test_learning_summary_splits_prioritize_and_deprioritize():
    history = [{
        "run_id": "run-1",
        "approved_by_section": {"launch": 3, "outbound": 1},
        "rejected_by_section": {"launch": 1, "outbound": 3},
        "counts": {ledger.APPROVED: 4, ledger.REJECTED: 4, ledger.EXECUTED: 0},
        "total_approved_spend_usd": 120,
    }]
    summary = ledger.learning_summary(history)
    assert summary["has_history"] is True
    assert summary["prior_sprints"] == 1
    assert "launch" in summary["prioritize_sections"]      # 0.75 >= 0.5
    assert "outbound" in summary["deprioritize_sections"]  # 0.25 < 0.5


def test_learning_summary_empty_history():
    summary = ledger.learning_summary([])
    assert summary["has_history"] is False
    assert summary["prioritize_sections"] == []
    assert summary["deprioritize_sections"] == []


# ---------------------------------------------------------------------------
# Integration: sprint_report seeds the draft state machine
# ---------------------------------------------------------------------------

def test_sprint_report_seeds_pending_draft(sprint):
    state = load_state(sprint["dir"])
    assert state["sprint_state"] == ledger.SPRINT_DRAFT
    assert len(state["items"]) == DEMO_ITEM_COUNT
    assert status_counts(state) == {ledger.PENDING: DEMO_ITEM_COUNT}


# ---------------------------------------------------------------------------
# Integration: the approvals.py CLI safety gate
# ---------------------------------------------------------------------------

def test_approve_all_blocked_before_finalize(sprint):
    result = approvals(sprint["profile"], "approve", "all")
    assert result.returncode == 1
    assert "locked" in result.stdout.lower()
    # Nothing changed: still all pending, still draft.
    state = load_state(sprint["dir"])
    assert state["sprint_state"] == ledger.SPRINT_DRAFT
    assert status_counts(state) == {ledger.PENDING: DEMO_ITEM_COUNT}


def test_finalize_unlocks_and_is_idempotent(sprint):
    r1 = approvals(sprint["profile"], "finalize")
    assert r1.returncode == 0
    assert load_state(sprint["dir"])["sprint_state"] == ledger.SPRINT_FINALIZED

    r2 = approvals(sprint["profile"], "finalize")
    assert r2.returncode == 0
    assert "already finalized" in r2.stdout.lower()


def test_approve_section_then_all(sprint):
    approvals(sprint["profile"], "finalize", check=True)

    r = approvals(sprint["profile"], "approve", "launch")
    assert r.returncode == 0
    state = load_state(sprint["dir"])
    approved = [it for it in state["items"] if it["status"] == ledger.APPROVED]
    assert approved and {it["section"] for it in approved} == {"launch"}
    pending_before = sum(1 for it in state["items"] if it["status"] == ledger.PENDING)
    assert pending_before == DEMO_ITEM_COUNT - len(approved)

    # `approve all` sweeps up the remaining pending items.
    r = approvals(sprint["profile"], "approve", "all")
    assert r.returncode == 0
    state = load_state(sprint["dir"])
    assert status_counts(state).get(ledger.PENDING, 0) == 0
    assert status_counts(state)[ledger.APPROVED] == DEMO_ITEM_COUNT


def test_reject_then_execute_approved(sprint):
    approvals(sprint["profile"], "finalize", check=True)
    state = load_state(sprint["dir"])
    launch_ids = [it["id"] for it in state["items"] if it["section"] == "launch"]

    # Reject one launch item straight from pending.
    r = approvals(sprint["profile"], "reject", launch_ids[0])
    assert r.returncode == 0
    assert ledger.find_item(load_state(sprint["dir"]), launch_ids[0])["status"] == ledger.REJECTED

    # Approve the rest of launch, then execute all approved items.
    approvals(sprint["profile"], "approve", "launch", check=True)
    r = approvals(sprint["profile"], "execute", "approved")
    assert r.returncode == 0
    counts = status_counts(load_state(sprint["dir"]))
    assert counts.get(ledger.EXECUTED, 0) == len(launch_ids) - 1
    assert counts.get(ledger.REJECTED, 0) == 1


def test_execute_nonapproved_item_is_rejected(sprint):
    approvals(sprint["profile"], "finalize", check=True)
    state = load_state(sprint["dir"])
    pending_id = state["items"][0]["id"]  # finalized but still pending
    r = approvals(sprint["profile"], "execute", pending_id)
    assert r.returncode == 1
    assert "approved" in r.stdout.lower()
    assert load_state(sprint["dir"])["items"][0]["status"] == ledger.PENDING


def test_status_renders_and_reflects_counts(sprint):
    approvals(sprint["profile"], "finalize", check=True)
    approvals(sprint["profile"], "approve", "launch", check=True)
    r = approvals(sprint["profile"], "status")
    assert r.returncode == 0
    assert "finalized" in r.stdout.lower()
    assert "approved" in r.stdout.lower()


# ---------------------------------------------------------------------------
# Integration: the cross-sprint learning loop end to end
# ---------------------------------------------------------------------------

def test_second_sprint_learns_from_first(sprint):
    # Engage sprint 1: finalize + approve the launch section.
    approvals(sprint["profile"], "finalize", check=True)
    approvals(sprint["profile"], "approve", "launch", check=True)

    # Start a new sprint (a new week): archives sprint 1 and seeds sprint 2
    # with learning. A plain re-compile would instead continue sprint 1.
    run([sys.executable, str(SCRIPTS / "sprint_report.py"),
         "--profile", str(sprint["profile"]), "--output-dir", str(sprint["out"]),
         "--new-sprint"])

    history = ledger.read_history(sprint["dir"])
    assert len(history) == 1
    rec = history[0]
    assert rec["approved_by_section"].get("launch", 0) >= 1
    assert "counts" in rec and "total_approved_spend_usd" in rec

    report = load_json(sprint["out"] / "weekly_flywheel_sprint.json")
    assert report["learning"]["has_history"] is True
    next_week = report["next_week_plan"]
    assert next_week["based_on"] == "prior_sprint_approvals"
    assert "vs_last_sprint" in next_week


# ---------------------------------------------------------------------------
# Integration: validate_outputs approval-gate enforcement
# ---------------------------------------------------------------------------

def validate(profile, out_dir, check=False):
    return run(
        [sys.executable, str(SCRIPTS / "validate_outputs.py"),
         "--profile", str(profile), "--output-dir", str(out_dir)],
        check=check,
    )


def test_validate_passes_on_fresh_draft(sprint):
    r = validate(sprint["profile"], sprint["out"])
    assert r.returncode == 0
    assert "All validations passed" in r.stdout


def test_validate_catches_executed_item_in_draft(sprint):
    # Tamper: mark an item executed while the sprint is still a draft.
    state_path = Path(sprint["dir"]) / ledger.STATE_FILENAME
    state = load_json(state_path)
    state["items"][0]["status"] = ledger.EXECUTED
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    r = validate(sprint["profile"], sprint["out"])
    assert r.returncode != 0
    assert "All validations passed" not in r.stdout
    out = r.stdout.lower()
    assert "approval gate" in out or "locked" in out or "finalize" in out


def test_validate_is_noop_without_state_file(sprint):
    # With no sprint_state.json beside the profile, check_approval_state is a
    # no-op and validation still passes on the demo artifacts.
    (Path(sprint["dir"]) / ledger.STATE_FILENAME).unlink()
    r = validate(sprint["profile"], sprint["out"])
    assert r.returncode == 0
    assert "All validations passed" in r.stdout
