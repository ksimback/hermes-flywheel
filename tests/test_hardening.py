"""Contract, research happy-path, CSV, and validator hardening tests.

Conventions mirror tests/test_completeness.py: a module-level ``run_script``
helper, session fixtures that build isolated pipeline outputs via
``tmp_path_factory``, and ``load_json``. Nothing is ever written into the
committed repo tree (demo/demo-output, data/) - all outputs go to tmp dirs.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"

DOWNSTREAM_PIPELINE = [
    "launch_plan.py",
    "backlink_hunter.py",
    "lead_scorer.py",
    "creator_campaign.py",
    "mpp_spend_planner.py",
    "trend_scan.py",
    "sprint_report.py",
    "validate_outputs.py",
]


def run_script(cmd, cwd=ROOT, check=False):
    """Run a pipeline script, capturing merged stdout/stderr as text."""
    return subprocess.run(
        [sys.executable] + [str(c) for c in cmd],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def real_profile(tmp_path_factory):
    """A real (non-demo) founder profile with a small single-spend guardrail."""
    out = tmp_path_factory.mktemp("real-profile")
    profile = out / "profile.json"
    result = run_script([
        SCRIPTS / "flywheel_intake.py",
        "Product: RealCo (https://realco.example) ICP: dev tool founders "
        "Competitors: acme.example, beta.example Budget: $200 "
        "Focus: launch Category: dev tools",
        "--output", profile,
    ])
    assert result.returncode == 0, result.stdout
    data = load_json(profile)
    assert data["demo_mode"] is False
    return {"path": profile, "data": data, "dir": out}


@pytest.fixture(scope="session")
def demo_out(tmp_path_factory):
    """A full demo pipeline run into an isolated tmp dir (for validator tests)."""
    out = tmp_path_factory.mktemp("hardening-demo")
    profile = out / "profile.json"
    result = run_script([
        SCRIPTS / "flywheel_intake.py", "--demo", "--output", profile,
    ])
    assert result.returncode == 0, result.stdout
    for script in DOWNSTREAM_PIPELINE:
        result = run_script([
            SCRIPTS / script, "--profile", profile, "--output-dir", out,
        ])
        assert result.returncode == 0, f"{script}: {result.stdout}"
    return {"out": out, "profile": profile}


def run_validator(profile, output_dir):
    return run_script([
        SCRIPTS / "validate_outputs.py",
        "--profile", profile, "--output-dir", output_dir,
    ])


# ---------------------------------------------------------------------------
# Contract: _common.py anchoring, profile loading, research resolution
# ---------------------------------------------------------------------------

def test_relative_output_dir_escaping_root_exits_1(real_profile, tmp_path):
    """A relative --output-dir with '..' that escapes ROOT must exit 1."""
    result = run_script([
        SCRIPTS / "launch_plan.py",
        "--profile", real_profile["path"],
        "--output-dir", "../flywheel_escape_should_fail",
    ])
    assert result.returncode == 1, result.stdout
    assert "escapes the repo root" in result.stdout


def test_missing_profile_exits_1_with_intake_hint(tmp_path):
    """load_profile: a missing --profile exits 1 and points at intake."""
    result = run_script([
        SCRIPTS / "launch_plan.py",
        "--profile", tmp_path / "nonexistent.json",
        "--output-dir", tmp_path / "out",
    ])
    assert result.returncode == 1, result.stdout
    assert "Product profile not found" in result.stdout
    assert "flywheel_intake.py" in result.stdout


@pytest.mark.parametrize("payload,label", [
    ({}, "missing-key-dict"),
    (["a", "b"], "bare-list-of-non-dicts"),
    ({"opportunities": []}, "valid-key-empty-list"),
])
def test_malformed_research_input_exits_1_with_schema_hint(real_profile, tmp_path, payload, label):
    """resolve_research rejects malformed --input with EXIT_ERROR + schema hint."""
    research = tmp_path / f"{label}.json"
    research.write_text(json.dumps(payload), encoding="utf-8")
    result = run_script([
        SCRIPTS / "backlink_hunter.py",
        "--profile", real_profile["path"],
        "--output-dir", tmp_path / "out",
        "--input", research,
    ])
    assert result.returncode == 1, result.stdout
    assert "Expected schema" in result.stdout


@pytest.mark.parametrize("bad_flag", [["--demo"], ["--input", "x.json"]])
def test_non_research_script_rejects_research_flags(real_profile, tmp_path, bad_flag):
    """build_parser(research=False) scripts must reject --demo/--input loudly."""
    result = run_script([
        SCRIPTS / "launch_plan.py",
        "--profile", real_profile["path"],
        "--output-dir", tmp_path / "out",
    ] + bad_flag)
    # argparse errors with exit code 2 - the flag is not silently ignored.
    assert result.returncode != 0
    assert result.returncode == 2


def test_scripts_work_from_cwd_outside_repo(real_profile, tmp_path):
    """Contract headline: absolute paths work from any cwd, even outside ROOT."""
    out_dir = tmp_path / "out"
    result = run_script(
        [
            SCRIPTS / "launch_plan.py",
            "--profile", real_profile["path"],
            "--output-dir", out_dir,
        ],
        cwd=tmp_path,  # deliberately outside the repo
    )
    assert result.returncode == 0, result.stdout
    assert (out_dir / "launch_plan.json").exists()


# ---------------------------------------------------------------------------
# Research happy-path across all research-consuming scripts
# ---------------------------------------------------------------------------

RESEARCH_CASES = [
    (
        "lead_scorer.py", "leads", "outbound_queue.json",
        {
            "name": "Dana Fox", "title": "Founder", "company": "RealDevCo",
            "bio": "Builds developer tools for early-stage teams.",
            "source": "LinkedIn engagement", "url": "https://realdir.example/dana",
            "engagement_context": "Asked about better dev tool workflows.",
        },
    ),
    (
        "creator_campaign.py", "creators", "creator_campaign.json",
        {
            "name": "DevToolReviewer", "platform": "YouTube", "followers": 20000,
            "niche": "dev tools", "engagement_rate": 5.5,
            "content_type": ["tool reviews"], "avg_views": 5000,
            "profile_url": "https://realdir.example/creator",
            "recent_content": "Reviews of developer tooling",
            "audience_match": "dev tool founders", "estimated_rate": 120,
        },
    ),
    (
        "trend_scan.py", "trends", "trend_content.json",
        {
            "trend": "AI-native dev tools", "platform": "Twitter/X", "volume": "high",
            "relevance": "developers adopting AI-native tooling",
            "example_post": "AI-native dev tools are eating the old stack.",
            "viral_potential": 80, "keywords": ["dev tools", "AI"],
        },
    ),
]


@pytest.mark.parametrize("script,key,outfile,item", RESEARCH_CASES)
def test_research_happy_path_produces_agent_research_artifact(
    real_profile, tmp_path, script, key, outfile, item
):
    research = tmp_path / f"{key}.json"
    research.write_text(json.dumps({key: [item]}), encoding="utf-8")
    out_dir = tmp_path / "out"
    result = run_script([
        SCRIPTS / script,
        "--profile", real_profile["path"],
        "--output-dir", out_dir,
        "--input", research,
    ])
    assert result.returncode == 0, result.stdout
    data = load_json(out_dir / outfile)
    assert data["data_source"] == "agent_research"
    assert data["demo_mode"] is False
    dumped = json.dumps(data)
    assert "example.com" not in dumped
    assert "ExampleAI" not in dumped


# ---------------------------------------------------------------------------
# lead_scorer CSV path
# ---------------------------------------------------------------------------

def test_leads_csv_produces_founder_csv_source(real_profile, tmp_path):
    csv_copy = tmp_path / "leads.csv"
    shutil.copyfile(ROOT / "data" / "leads.example.csv", csv_copy)
    out_dir = tmp_path / "out"
    result = run_script([
        SCRIPTS / "lead_scorer.py",
        "--profile", real_profile["path"],
        "--output-dir", out_dir,
        "--leads-csv", csv_copy,
    ])
    assert result.returncode == 0, result.stdout
    data = load_json(out_dir / "outbound_queue.json")
    assert data["data_source"] == "founder_csv"
    assert data["total_leads"] >= 1


def test_missing_leads_csv_exits_2(real_profile, tmp_path):
    result = run_script([
        SCRIPTS / "lead_scorer.py",
        "--profile", real_profile["path"],
        "--output-dir", tmp_path / "out",
        "--leads-csv", tmp_path / "does_not_exist.csv",
    ])
    assert result.returncode == 2, result.stdout
    assert "not found" in result.stdout.lower()


def test_ragged_csv_row_does_not_crash(real_profile, tmp_path):
    """Regression: DictReader yields None for missing columns; must normalize."""
    csv_path = tmp_path / "ragged.csv"
    csv_path.write_text(
        "name,title,company,bio,source,url,engagement_context\n"
        "Bob,Founder,Acme\n",  # only 3 of 7 columns
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    result = run_script([
        SCRIPTS / "lead_scorer.py",
        "--profile", real_profile["path"],
        "--output-dir", out_dir,
        "--leads-csv", csv_path,
    ])
    assert result.returncode == 0, result.stdout
    assert "Traceback" not in result.stdout
    data = load_json(out_dir / "outbound_queue.json")
    assert data["total_leads"] == 1


# ---------------------------------------------------------------------------
# creator_campaign spend guardrail (downward-only clamp regression)
# ---------------------------------------------------------------------------

def test_creator_spend_never_exceeds_base_fee_or_single_spend_limit(real_profile, tmp_path):
    max_single = real_profile["data"]["budget"]["max_single_spend_usd"]
    assert max_single > 0
    creators = {
        "creators": [
            {
                "name": "CheapCreator", "platform": "YouTube", "followers": 5000,
                "niche": "dev tools", "engagement_rate": 4.0,
                "content_type": ["tool reviews"], "avg_views": 1000,
                "profile_url": "https://realdir.example/cheap",
                "recent_content": "dev tool reviews",
                "audience_match": "dev tool founders", "estimated_rate": 40,
            },
            {
                "name": "PriceyCreator", "platform": "YouTube", "followers": 90000,
                "niche": "dev tools", "engagement_rate": 6.0,
                "content_type": ["tool reviews"], "avg_views": 30000,
                "profile_url": "https://realdir.example/pricey",
                "recent_content": "dev tool reviews",
                "audience_match": "dev tool founders", "estimated_rate": 400,
            },
        ]
    }
    research = tmp_path / "creators.json"
    research.write_text(json.dumps(creators), encoding="utf-8")
    out_dir = tmp_path / "out"
    result = run_script([
        SCRIPTS / "creator_campaign.py",
        "--profile", real_profile["path"],
        "--output-dir", out_dir,
        "--input", research,
    ])
    assert result.returncode == 0, result.stdout
    data = load_json(out_dir / "creator_campaign.json")
    base_fee_by_creator = {
        p["creator"]: p["pricing"]["base_fee"] for p in data["campaign_proposals"]
    }
    assert data["spend_requests"], "expected at least one spend request"
    for req in data["spend_requests"]:
        amount = req["amount_usd"]
        # Never clamped UP above what the creator charges...
        assert amount <= base_fee_by_creator[req["creator"]]
        # ...and never above the founder's single-spend guardrail.
        assert amount <= max_single


# ---------------------------------------------------------------------------
# Validator: secret detection across patterns + honesty branches
# ---------------------------------------------------------------------------

SECRET_SAMPLES = [
    ("aws", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"'),
    ("slack", 'slack = "xoxb-123456789012-AbCdEfGhIjKl"'),
    ("github", 'gh = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"'),
    ("private_key", "-----BEGIN PRIVATE KEY-----"),
]


@pytest.mark.parametrize("label,secret", SECRET_SAMPLES)
def test_validator_catches_planted_secret_in_markdown(demo_out, tmp_path, label, secret):
    seeded = tmp_path / f"seeded-{label}"
    shutil.copytree(demo_out["out"], seeded)
    target = seeded / "weekly_flywheel_sprint.md"
    target.write_text(
        target.read_text(encoding="utf-8") + f"\n{secret}\n", encoding="utf-8"
    )
    result = run_validator(demo_out["profile"], seeded)
    assert result.returncode != 0, result.stdout
    assert "All validations passed" not in result.stdout


def test_validator_catches_planted_secret_in_json_artifact(demo_out, tmp_path):
    seeded = tmp_path / "seeded-json"
    shutil.copytree(demo_out["out"], seeded)
    target = seeded / "trend_content.json"
    data = load_json(target)
    data["_planted_secret"] = "AKIAIOSFODNN7EXAMPLE"
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = run_validator(demo_out["profile"], seeded)
    assert result.returncode != 0, result.stdout
    assert "All validations passed" not in result.stdout


def test_validator_false_positive_guard(demo_out, tmp_path):
    """Fixture domains and bare credential keywords must NOT trip detection."""
    seeded = tmp_path / "seeded-clean"
    shutil.copytree(demo_out["out"], seeded)
    (seeded / "notes.md").write_text(
        "Visit https://example.com and ask the team for a token to continue.\n",
        encoding="utf-8",
    )
    result = run_validator(demo_out["profile"], seeded)
    assert result.returncode == 0, result.stdout
    assert "All validations passed" in result.stdout


def test_validator_simulated_false_is_hard_fail(demo_out, tmp_path):
    seeded = tmp_path / "seeded-sim-false"
    shutil.copytree(demo_out["out"], seeded)
    target = seeded / "mpp_spend_cards.json"
    data = load_json(target)
    data["simulated"] = False
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = run_validator(demo_out["profile"], seeded)
    assert result.returncode != 0, result.stdout
    assert "All validations passed" not in result.stdout


def test_validator_missing_simulated_marker_warns_but_passes(demo_out, tmp_path):
    seeded = tmp_path / "seeded-sim-absent"
    shutil.copytree(demo_out["out"], seeded)
    target = seeded / "mpp_spend_cards.json"
    data = load_json(target)
    data.pop("simulated", None)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = run_validator(demo_out["profile"], seeded)
    assert result.returncode == 0, result.stdout
    assert "All validations passed" in result.stdout
    assert "missing 'simulated'" in result.stdout
