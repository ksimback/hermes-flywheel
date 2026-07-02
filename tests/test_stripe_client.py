"""Unit tests for stripe_client.py and the mpp_spend_planner integration.

Conventions mirror tests/test_units.py (sys.path-insert + direct import) and
tests/test_completeness.py / tests/test_hardening.py (subprocess `run` helper,
`load_json`). No real network calls are ever made or tested here -- only the
no-key and stubbed-success/failure code paths.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import stripe_client  # noqa: E402
import mpp_spend_planner  # noqa: E402
import validate_outputs  # noqa: E402


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


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# get_test_key / available
# ---------------------------------------------------------------------------

class TestGetTestKey:
    def test_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        assert stripe_client.get_test_key() is None
        assert stripe_client.available() is False

    def test_placeholder_returns_none(self, monkeypatch):
        monkeypatch.setenv("STRIPE_API_KEY", "replace_with_stripe_test_key")
        assert stripe_client.get_test_key() is None
        assert stripe_client.available() is False

    def test_live_key_is_refused(self, monkeypatch, capsys):
        monkeypatch.setenv("STRIPE_API_KEY", "sk_live_ABC")
        assert stripe_client.get_test_key() is None
        assert stripe_client.available() is False
        assert "not a test key" in capsys.readouterr().out

    def test_test_key_is_accepted(self, monkeypatch):
        monkeypatch.setenv("STRIPE_API_KEY", "sk_test_ABC")
        assert stripe_client.get_test_key() == "sk_test_ABC"
        assert stripe_client.available() is True


# ---------------------------------------------------------------------------
# create_authorization_intent guard clauses (no network calls exercised)
# ---------------------------------------------------------------------------

class TestCreateAuthorizationIntentGuards:
    def test_no_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        result = stripe_client.create_authorization_intent(1000)
        assert "error" in result

    @pytest.mark.parametrize("amount", [-100, 0, "1000"])
    def test_bad_amount_returns_error_without_network_call(self, monkeypatch, amount):
        monkeypatch.setenv("STRIPE_API_KEY", "sk_test_ABC")
        result = stripe_client.create_authorization_intent(amount)
        assert "error" in result

    def test_dashboard_url_format(self):
        assert stripe_client.dashboard_url("pi_123") == (
            "https://dashboard.stripe.com/test/payments/pi_123"
        )


# ---------------------------------------------------------------------------
# mpp_spend_planner.build_receipts
# ---------------------------------------------------------------------------

def _make_cards():
    return [
        {
            "id": "mpp_creator_001",
            "amount_cents": 7500,
            "currency": "usd",
            "http_endpoint": "https://mpp.example.ai/resources/creator-test",
            "amount_usd": 75,
            "resource_type": "creator_test",
        },
        {
            "id": "mpp_data_001",
            "amount_cents": 1200,
            "currency": "usd",
            "http_endpoint": "https://mpp.example.ai/resources/competitor-demand-report",
            "amount_usd": 12,
            "resource_type": "competitor_demand_data",
        },
    ]


class TestBuildReceiptsSimulated:
    def test_no_key_all_simulated(self, monkeypatch):
        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        cards = _make_cards()
        receipts, used_stripe = mpp_spend_planner.build_receipts(cards)
        assert used_stripe is False
        assert len(receipts) == len(cards)
        for receipt in receipts:
            assert receipt["simulated"] is True
            assert receipt["payment_intent"].startswith("pi_test_mpp_")


class TestBuildReceiptsRealStripe:
    def test_stubbed_success(self, monkeypatch):
        monkeypatch.setattr(stripe_client, "available", lambda: True)

        def fake_create(amount_cents, currency="usd", metadata=None, timeout=15):
            return {
                "id": "pi_test_REAL_1",
                "status": "requires_payment_method",
                "dashboard_url": "https://dashboard.stripe.com/test/payments/pi_test_REAL_1",
                "mode": "test",
            }

        monkeypatch.setattr(stripe_client, "create_authorization_intent", fake_create)
        cards = _make_cards()
        receipts, used_stripe = mpp_spend_planner.build_receipts(cards[:1])
        assert used_stripe is True
        receipt = receipts[0]
        assert receipt["simulated"] is False
        assert receipt["payment_intent"] == "pi_test_REAL_1"
        assert receipt["status"] == "authorization_pending_founder_approval"

    def test_stubbed_error_falls_back_to_simulated(self, monkeypatch):
        monkeypatch.setattr(stripe_client, "available", lambda: True)
        monkeypatch.setattr(
            stripe_client,
            "create_authorization_intent",
            lambda *a, **k: {"error": "stripe HTTP 402: card declined"},
        )
        cards = _make_cards()
        receipts, used_stripe = mpp_spend_planner.build_receipts(cards)
        assert used_stripe is False
        for receipt in receipts:
            assert receipt["simulated"] is True


# ---------------------------------------------------------------------------
# validate_outputs.check_simulated_marker
# ---------------------------------------------------------------------------

class TestCheckSimulatedMarker:
    def test_simulated_true_is_honest(self):
        warnings = []
        issues = validate_outputs.check_simulated_marker(
            {"simulated": True}, "label", warnings
        )
        assert issues == []
        assert warnings == []

    def test_simulated_false_with_stripe_test_mode_is_honest(self):
        warnings = []
        issues = validate_outputs.check_simulated_marker(
            {"simulated": False, "stripe_test_mode": True}, "label", warnings
        )
        assert issues == []
        assert warnings == []

    def test_bare_simulated_false_is_an_issue(self):
        warnings = []
        issues = validate_outputs.check_simulated_marker(
            {"simulated": False}, "label", warnings
        )
        assert len(issues) == 1
        assert warnings == []


# ---------------------------------------------------------------------------
# Integration: full demo pipeline with STRIPE_API_KEY unset
# ---------------------------------------------------------------------------

def test_demo_pipeline_no_stripe_key_is_simulated_and_validates(tmp_path, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)

    out_dir = tmp_path / "out"
    profile = out_dir / "profile.json"

    result = run([
        sys.executable, str(SCRIPTS / "flywheel_intake.py"),
        "--demo", "--output", str(profile),
    ])
    assert "Traceback" not in result.stdout

    downstream = [
        "launch_plan.py", "backlink_hunter.py", "lead_scorer.py",
        "creator_campaign.py", "mpp_spend_planner.py", "trend_scan.py",
        "sprint_report.py",
    ]
    for script in downstream:
        result = run([
            sys.executable, str(SCRIPTS / script),
            "--profile", str(profile), "--output-dir", str(out_dir),
        ])
        assert "Traceback" not in result.stdout, f"{script}: {result.stdout}"

    receipts = load_json(out_dir / "mpp_receipts.json")
    assert receipts["simulated"] is True
    assert receipts["stripe_test_mode"] is False

    validate_result = run([
        sys.executable, str(SCRIPTS / "validate_outputs.py"),
        "--profile", str(profile), "--output-dir", str(out_dir),
    ], check=False)
    assert validate_result.returncode == 0, validate_result.stdout
    assert "All validations passed" in validate_result.stdout
