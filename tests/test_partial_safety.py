"""Regression tests for the v0.4.0 adversarial-review findings.

The --partial validation mode (used by flywheel.py for real headless runs)
must downgrade ONLY completeness thresholds, never safety invariants -- and
that classification must be by explicit type, not by matching English text
that an attacker-controlled string could spoof. flywheel.py must also never
report a crashed stage as success.
"""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "flywheel-agent" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import validate_outputs as vo  # noqa: E402
from validate_outputs import Completeness  # noqa: E402
import flywheel  # noqa: E402


# ---------------------------------------------------------------------------
# Explicit-typing: completeness vs safety issues
# ---------------------------------------------------------------------------

def _write(tmp, name, obj):
    p = tmp / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_low_competitor_count_is_completeness(tmp_path):
    p = _write(tmp_path, "profile.json", {
        "product_name": "X", "url": "https://x.co", "one_liner": "y", "category": "c",
        "icp": {"buyer": "b", "pain_points": ["p"]}, "competitors": ["only-one"],
        "positioning": {}, "budget": {"weekly_usd": 100, "max_single_spend_usd": 25, "requires_approval": True},
    })
    issues = vo.validate_product_profile(p)
    comp = [i for i in issues if "competitor" in i.lower()]
    assert comp and all(isinstance(i, Completeness) for i in comp)


def test_missing_approval_is_not_completeness_even_with_marker_name(tmp_path):
    """Finding B: a CRITICAL approval failure must stay a plain (hard) string
    even when a data-controlled field contains a completeness marker word."""
    p = _write(tmp_path, "outbound_queue.json", {
        "total_leads": 1,
        "leads": [{
            "name": "Expected Corp",  # contains a former "marker" substring
            "requires_human_approval": False,   # the safety violation
            "message_drafts": {"a": "hi"},
        }],
    })
    issues = vo.validate_outbound_queue(p)
    approval_issues = [i for i in issues if "approval" in i.lower()]
    assert approval_issues, "should flag the missing approval"
    assert all(not isinstance(i, Completeness) for i in approval_issues)


def test_non_test_mode_mpp_challenge_is_not_completeness(tmp_path):
    cards = _write(tmp_path, "mpp_spend_cards.json", {
        "protocol": "stripe_mpp", "simulated": True, "total_spend_cards": 1,
        "spend_cards": [{
            "id": "mpp_1", "protocol": "stripe_mpp", "status": "awaiting_founder_approval",
            "approval_command": "approve mpp_1", "amount_usd": 10, "amount_cents": 1000, "currency": "usd",
            "payment_challenge": {"http_status": 402, "test_mode": False},  # violation
            "founder_guardrails": {"autonomous_spend_limit_usd": 0},
        }],
    })
    receipts = _write(tmp_path, "mpp_receipts.json", {
        "protocol": "stripe_mpp", "mode": "test", "simulated": True, "total_receipts": 1,
        "receipts": [{"receipt_id": "r1", "spend_card_id": "mpp_1", "protocol": "stripe_mpp",
                      "mode": "test", "simulated": True, "payment_intent": "pi_test_mpp_000001"}],
    })
    warnings = []
    issues = vo.validate_mpp_spend_cards(cards, receipts, warnings, 100)
    challenge_issues = [i for i in issues if "402" in i or "test-mode" in i.lower()]
    assert challenge_issues
    assert all(not isinstance(i, Completeness) for i in challenge_issues)


def test_real_stripe_intent_passes_validation(tmp_path):
    """Codex #4: a real Stripe test intent (pi_...) is a valid test payment
    intent, not only the simulated pi_test_mpp_ form."""
    cards = _write(tmp_path, "mpp_spend_cards.json", {
        "protocol": "stripe_mpp", "simulated": True, "total_spend_cards": 1,
        "spend_cards": [{
            "id": "mpp_1", "protocol": "stripe_mpp", "status": "awaiting_founder_approval",
            "approval_command": "approve mpp_1", "amount_usd": 10, "amount_cents": 1000, "currency": "usd",
            "payment_challenge": {"http_status": 402, "test_mode": True},
            "founder_guardrails": {"autonomous_spend_limit_usd": 0},
        }],
    })
    receipts = _write(tmp_path, "mpp_receipts.json", {
        "protocol": "stripe_mpp", "mode": "test", "simulated": False, "stripe_test_mode": True,
        "total_receipts": 1,
        "receipts": [{"receipt_id": "r1", "spend_card_id": "mpp_1", "protocol": "stripe_mpp",
                      "mode": "test", "simulated": False, "stripe_test_mode": True,
                      "payment_intent": "pi_3ABCRealTestIntent"}],
    })
    warnings = []
    issues = vo.validate_mpp_spend_cards(cards, receipts, warnings, 100)
    assert not [i for i in issues if "payment intent" in i.lower()]


# ---------------------------------------------------------------------------
# flywheel.py: a crashed stage is never reported as success
# ---------------------------------------------------------------------------

class _Args:
    demo = True
    context = None
    profile = "p.json"
    output_dir = "o"
    new_sprint = False


def test_crashed_stage_fails_the_run(monkeypatch):
    """Finding D: a stage crash (exit 1) must fail the run, not be swallowed."""
    def fake_run(script, *a):
        return 1 if "mpp_spend_planner" in script else 0
    monkeypatch.setattr(flywheel, "_run", fake_run)
    assert flywheel.cmd_run(_Args()) == 1


def test_all_stages_ok_returns_success(monkeypatch):
    monkeypatch.setattr(flywheel, "_run", lambda script, *a: 0)
    assert flywheel.cmd_run(_Args()) == 0


def test_skipped_stage_exit2_is_not_a_crash(monkeypatch):
    """A real run where research stages exit 2 (no input) is partial, not
    failed: validate returns 0 in --partial, so the run returns 0."""
    args = _Args()
    args.demo = False
    args.context = "Product: Z (https://z.co) ICP: founders Budget: $100 Focus: launch"

    def fake_run(script, *a):
        # research-backed stages report "no input"; validate passes (partial)
        if any(s in script for s in ("backlink_hunter", "lead_scorer", "creator_campaign", "trend_scan", "research.py")):
            return 2
        return 0
    monkeypatch.setattr(flywheel, "_run", fake_run)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    assert flywheel.cmd_run(args) == 0
