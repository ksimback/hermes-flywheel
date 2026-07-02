"""Tests for the flywheel.py one-command entrypoint (Phase 4).

Conventions mirror tests/test_completeness.py and tests/test_hardening.py: a
module-level ``run`` subprocess helper, ``load_json``, and tmp_path-isolated
output directories (nothing is ever written into the committed repo tree).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"
FLYWHEEL = SCRIPTS / "flywheel.py"


def run(cmd, check=False, env=None):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
        env=env,
    )


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def test_doctor_exits_0_and_reports_env(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    result = run([sys.executable, str(FLYWHEEL), "doctor"])
    assert result.returncode == 0, result.stdout
    assert "Flywheel doctor" in result.stdout
    assert "Python" in result.stdout
    assert "SERPER_API_KEY" in result.stdout
    assert "STRIPE_API_KEY" in result.stdout


def test_run_demo_produces_full_sprint_and_validates(tmp_path):
    out_dir = tmp_path / "out"
    profile = tmp_path / "p.json"
    result = run([
        sys.executable, str(FLYWHEEL), "run", "--demo",
        "--profile", str(profile), "--output-dir", str(out_dir),
    ])
    assert result.returncode == 0, result.stdout
    assert (out_dir / "weekly_flywheel_sprint.md").exists()
    assert (out_dir / "mpp_receipts.json").exists()
    assert (out_dir / "launch_plan.json").exists()

    sprint = load_json(out_dir / "weekly_flywheel_sprint.json")
    assert "learning" in sprint


def test_run_no_context_no_demo_exits_2_with_guidance():
    result = run([sys.executable, str(FLYWHEEL), "run"])
    assert result.returncode == 2, result.stdout
    assert "Provide product context" in result.stdout


def test_run_with_leads_csv_produces_founder_outbound(tmp_path, monkeypatch):
    """A founder can point --leads-csv at their own file (not only data/leads.csv)
    and get warm outbound sourced from it."""
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    leads = tmp_path / "myleads.csv"
    leads.write_text((ROOT / "data" / "leads.example.csv").read_text(encoding="utf-8"),
                     encoding="utf-8")
    out_dir = tmp_path / "out"
    profile = tmp_path / "p.json"
    result = run([
        sys.executable, str(FLYWHEEL), "run",
        "Product: MyCo (https://myco.example) ICP: founders Budget: $300 Focus: outbound",
        "--profile", str(profile), "--output-dir", str(out_dir),
        "--leads-csv", str(leads),
    ])
    assert result.returncode == 0, result.stdout
    outbound = load_json(out_dir / "outbound_queue.json")
    assert outbound["data_source"] == "founder_csv"
    assert outbound["total_leads"] >= 1


def test_doctor_flags_live_key_as_refused(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_live_ABC")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    result = run([sys.executable, str(FLYWHEEL), "doctor"])
    assert result.returncode == 0, result.stdout
    assert "NOT a test key" in result.stdout


def test_real_run_without_keys_or_csv_skips_gracefully(tmp_path, monkeypatch):
    """A real (non-demo) run with no SERPER/STRIPE keys and no data/leads.csv
    skips the research-backed stages gracefully and still compiles the sprint.

    A partial sprint is a legitimate outcome, not a failure: flywheel.py
    validates in --partial mode, where intentionally-missing artifacts and
    completeness thresholds are warnings, so the run exits 0. Safety, secret,
    and approval checks stay strict even in partial mode (covered elsewhere).
    """
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    assert not (ROOT / "data" / "leads.csv").exists(), (
        "data/leads.csv must not exist in the repo for this test to be valid"
    )

    out_dir = tmp_path / "out"
    profile = tmp_path / "p.json"
    result = run([
        sys.executable, str(FLYWHEEL), "run",
        "Product: RealCo (https://realco.example) ICP: dev tool founders "
        "Competitors: acme.example, beta.example Budget: $100 Focus: launch",
        "--profile", str(profile), "--output-dir", str(out_dir),
    ])

    assert "Partial sprint" in result.stdout
    assert "Skipped" in result.stdout
    assert (out_dir / "weekly_flywheel_sprint.md").exists()
    assert result.returncode == 0, result.stdout
