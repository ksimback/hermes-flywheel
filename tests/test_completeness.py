import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"

REQUIRED_FILES = [
    "distribution.yaml",
    "SOUL.md",
    "config.yaml",
    "mcp.json",
    ".env.EXAMPLE",
    ".gitignore",
    "README.md",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "cron/weekly-gtm-sprint.json",
    "skills/flywheel-agent/SKILL.md",
    "skills/flywheel-agent/templates/sample-product.md",
    "skills/flywheel-agent/templates/sample-competitors.txt",
    "skills/flywheel-agent/templates/weekly-sprint-template.md",
    "docs/distribution.md",
    "docs/technical-spec.md",
    "docs/testing-plan.md",
    "docs/slack-gtm-employee.md",
    "docs/sponsor-integrations.md",
]

REQUIRED_SCRIPTS = [
    "_common.py",
    "flywheel_intake.py",
    "launch_plan.py",
    "backlink_hunter.py",
    "lead_scorer.py",
    "creator_campaign.py",
    "mpp_spend_planner.py",
    "trend_scan.py",
    "sprint_report.py",
    "validate_outputs.py",
]

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


def read_repo_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def demo_run(tmp_path_factory):
    """Run the full demo pipeline once into an isolated directory.

    Returns a dict with the output dir, profile path, and per-script stdout.
    Nothing is written into the committed repo tree.
    """
    out_dir = tmp_path_factory.mktemp("demo-out")
    profile = out_dir / "profile.json"
    stdouts = {}

    result = run([
        sys.executable, str(SCRIPTS / "flywheel_intake.py"),
        "--demo", "--output", str(profile),
    ])
    stdouts["flywheel_intake.py"] = result.stdout

    for script in DOWNSTREAM_PIPELINE:
        result = run([
            sys.executable, str(SCRIPTS / script),
            "--profile", str(profile),
            "--output-dir", str(out_dir),
        ])
        stdouts[script] = result.stdout

    return {"out": out_dir, "profile": profile, "stdout": stdouts}


# ---------------------------------------------------------------------------
# Distribution completeness and public-repo hygiene
# ---------------------------------------------------------------------------

def test_distribution_file_completeness():
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    missing += [f"skills/flywheel-agent/scripts/{name}" for name in REQUIRED_SCRIPTS if not (SCRIPTS / name).exists()]
    assert missing == []


def test_distribution_manifest_and_readme_install_path():
    manifest = read_repo_text("distribution.yaml")
    assert "name: flywheel-agent" in manifest
    assert "hermes_requires" in manifest
    assert "NVIDIA_API_KEY" in manifest
    assert "STRIPE_API_KEY" in manifest
    assert "SERPER_API_KEY" in manifest

    readme = read_repo_text("README.md")
    assert "hermes profile install" in readme
    assert "hermes profile install github.com/ksimback/hermes-flywheel --alias --yes" in readme
    assert "--alias flywheel-agent" not in readme
    assert "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash" in readme
    assert "hermes -p flywheel-agent setup --portal" in readme
    assert "flywheel-agent chat" in readme
    assert "installable Hermes Agent profile" in readme
    assert "Slack and Telegram" in readme
    assert "docs/slack-gtm-employee.md" in readme


def test_prompts_enforce_honest_data_provenance():
    soul = read_repo_text("SOUL.md")
    skill = read_repo_text("skills/flywheel-agent/SKILL.md")
    public_prompt_text = soul + "\n" + skill

    forbidden_terms = [
        "Orbit" + "Kit",
        "Forge" + "AI",
        "Space" + "Tech",
        "Rocket" + " Labs",
    ]
    for term in forbidden_terms:
        assert term not in public_prompt_text

    # Honesty guardrails: fixtures only for explicit demos, and the agent
    # must disclose when live research is unavailable.
    assert "Fixture data is only used for explicit demos" in soul
    assert "say so plainly" in soul
    assert "Never present sample data as real research" in soul
    assert "Never present sample data as real research" in skill

    # The old concealment instructions must be gone.
    forbidden_instructions = [
        "Do not mention demo mode",
        "Never mention fixture names",
        "simply acknowledge the sprint and proceed",
    ]
    for phrase in forbidden_instructions:
        assert phrase not in public_prompt_text


def test_public_repo_excludes_landing_page_and_marketing_assets():
    removed = [
        "index" + ".html",
        "landing" + "-taste.html",
        "ver" + "cel.json",
        "media/flywheel" + "-demo.mp4",
        "media/flywheel" + "-demo-poster.jpg",
        "scripts/render" + "_demo_video.py",
        "docs/submission" + "-notes.md",
        "demo/demo" + "-script.md",
    ]
    present = [path for path in removed if (ROOT / path).exists()]
    assert present == []

    readme = read_repo_text("README.md").lower()
    assert "hermesflywheel.com" in readme
    assert "request" + "-access" not in readme
    assert "ver" + "cel" not in readme


def test_public_install_docs_are_focused_on_profile_distribution():
    readme = read_repo_text("README.md")
    manifest = read_repo_text("distribution.yaml")
    assert "github.com/ksimback/hermes-flywheel" in readme
    assert "https://hermesflywheel.com" in manifest
    assert "SOUL.md" in readme
    assert "skills/flywheel-agent/SKILL.md" in readme
    assert "demo/demo-output/weekly_flywheel_sprint.md" in readme
    assert "docs/slack-gtm-employee.md" in readme
    assert "No autonomous spend" in readme
    assert "fixture data is only used" in readme.lower()


def test_user_owned_state_and_secret_files_are_not_present():
    forbidden = [
        ".env",
        "auth.json",
        "state.db",
        "sessions",
        "memories",
    ]
    present = [path for path in forbidden if (ROOT / path).exists()]
    assert present == []

    gitignore = read_repo_text(".gitignore")
    for pattern in [".env", "auth.json", "memories/", "sessions/", "state.db"]:
        assert pattern in gitignore


def test_python_scripts_compile():
    run([sys.executable, "-m", "compileall", "-q", "skills/flywheel-agent/scripts"])


def test_committed_demo_artifacts_exist():
    for name in [
        "launch_plan.json", "backlink_opportunities.json", "outbound_queue.json",
        "creator_campaign.json", "mpp_spend_cards.json", "mpp_receipts.json",
        "trend_content.json", "weekly_flywheel_sprint.json", "weekly_flywheel_sprint.md",
        "runs/latest_run.json",
    ]:
        assert (ROOT / "demo/demo-output" / name).exists(), name


# ---------------------------------------------------------------------------
# Intake behavior
# ---------------------------------------------------------------------------

def test_intake_refuses_silent_fixture_without_input(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "flywheel_intake.py"),
         "--output", str(tmp_path / "profile.json")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0
    assert "No product context provided" in result.stdout
    assert "--demo" in result.stdout


def test_intake_uses_real_founder_context(tmp_path):
    profile_path = tmp_path / "exampleai_profile.json"
    result = run([
        sys.executable,
        str(SCRIPTS / "flywheel_intake.py"),
        "Product: ExampleAI (https://example.ai) ICP: e-commerce founders Competitors: cartpilot.example Budget: $50 Focus: ExampleAI launch awareness",
        "--output",
        str(profile_path),
    ])
    assert "Using founder-provided product context" in result.stdout
    profile = load_json(profile_path)
    assert profile["product_name"] == "ExampleAI"
    assert profile["url"] == "https://example.ai"
    assert profile["demo_mode"] is False
    # Internal review notes must not masquerade as marketing proof points.
    assert profile["positioning"]["proof_points"] == []
    assert profile["positioning"].get("review_notes")
    assert "Orbit" + "Kit" not in json.dumps(profile)
    assert "Forge" + "AI" not in json.dumps(profile)


def test_real_mode_requires_agent_research_input(tmp_path):
    """Non-demo runs must never silently fall back to fixture data."""
    profile_path = tmp_path / "profile.json"
    run([
        sys.executable, str(SCRIPTS / "flywheel_intake.py"),
        "Product: RealCo (https://realco.example) ICP: dev tool founders Competitors: acme.example Budget: $100 Focus: launch",
        "--output", str(profile_path),
    ])
    for script in ["backlink_hunter.py", "lead_scorer.py", "creator_campaign.py", "trend_scan.py"]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script),
             "--profile", str(profile_path),
             "--output-dir", str(tmp_path / "out")],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert result.returncode == 2, f"{script} should exit 2 without research input:\n{result.stdout}"
        assert "--input" in result.stdout


def test_real_mode_accepts_agent_research_input(tmp_path):
    profile_path = tmp_path / "profile.json"
    run([
        sys.executable, str(SCRIPTS / "flywheel_intake.py"),
        "Product: RealCo (https://realco.example) ICP: dev tool founders Competitors: acme.example Budget: $100 Focus: launch",
        "--output", str(profile_path),
    ])
    research = tmp_path / "opportunities.json"
    research.write_text(json.dumps({
        "opportunities": [
            {
                "id": "opp_real_001",
                "type": "directory_listing",
                "source_url": "https://realdir.example/devtools",
                "title": "Dev tools directory",
                "description": "Directory of developer tools",
                "why_relevant": "ICP researches tools here",
                "estimated_effort": "low",
                "estimated_impact": "high",
                "recommended_action": "Submit RealCo listing",
                "outreach_template": "Hi team, please consider adding RealCo.",
            }
        ]
    }), encoding="utf-8")
    out_dir = tmp_path / "out"
    run([
        sys.executable, str(SCRIPTS / "backlink_hunter.py"),
        "--profile", str(profile_path),
        "--output-dir", str(out_dir),
        "--input", str(research),
    ])
    data = load_json(out_dir / "backlink_opportunities.json")
    assert data["demo_mode"] is False
    assert data["data_source"] == "agent_research"
    assert data["total_opportunities"] >= 1
    dumped = json.dumps(data)
    assert "example.com" not in dumped  # no fixture leakage into real runs


# ---------------------------------------------------------------------------
# Demo pipeline acceptance criteria (isolated run)
# ---------------------------------------------------------------------------

def test_full_demo_pipeline_runs_without_paid_keys(demo_run):
    for script, stdout in demo_run["stdout"].items():
        assert "Traceback" not in stdout, f"{script} printed a traceback"


def test_generated_outputs_meet_acceptance_criteria(demo_run):
    out = demo_run["out"]
    launch = load_json(out / "launch_plan.json")
    backlinks = load_json(out / "backlink_opportunities.json")
    outbound = load_json(out / "outbound_queue.json")
    creators = load_json(out / "creator_campaign.json")
    mpp_cards = load_json(out / "mpp_spend_cards.json")
    mpp_receipts = load_json(out / "mpp_receipts.json")
    trends = load_json(out / "trend_content.json")
    sprint = load_json(out / "weekly_flywheel_sprint.json")

    assert len(launch["launch_channels"]) >= 6
    assert backlinks["total_opportunities"] >= 10
    assert outbound["total_leads"] >= 10
    assert creators["total_proposals"] >= 1
    assert mpp_cards["protocol"] == "stripe_mpp"
    assert mpp_cards["total_spend_cards"] >= 3
    assert mpp_cards["simulated"] is True
    assert mpp_receipts["simulated"] is True
    assert mpp_receipts["total_receipts"] == mpp_cards["total_spend_cards"]
    assert trends["total_content_pieces"] >= 5
    assert "next_week_plan" in sprint
    assert sprint["slack_callback_policy"]["quiet_by_default"] is True
    assert "draft_review_dashboard" in sprint["slack_callback_policy"]["post_to_thread"]
    assert sprint["draft_review_flow"]["default_mode"] == "dashboard"
    assert sprint["draft_review_flow"]["walkthrough_command"] == "start walkthrough"
    assert sprint["draft_review_flow"]["execution_locked_until_finalized"] is True
    assert "help_message" in sprint["slack_callback_policy"]["post_to_thread"]
    assert sprint["help_catalog"]["trigger_commands"] == ["help", "what can you do?", "commands", "capabilities"]
    assert "Draft weekly GTM sprints" in sprint["help_catalog"]["capabilities"][0]
    assert {section["review_command"] for section in sprint["review_sections"]} >= {"review launch", "review backlinks", "review outbound", "review content", "review budget", "review mpp spend"}
    assert {action["thread_command"] for action in sprint["thread_actions"]} >= {"help", "start walkthrough", "finalize sprint", "show approvals", "review launch"}

    # Demo provenance must be labeled, not hidden.
    for artifact in (backlinks, outbound, creators, trends):
        assert artifact["demo_mode"] is True
        assert artifact["data_source"] == "sample_fixture"


def test_outbound_and_spend_are_approval_gated(demo_run):
    out = demo_run["out"]
    outbound = load_json(out / "outbound_queue.json")
    creators = load_json(out / "creator_campaign.json")
    mpp_cards = load_json(out / "mpp_spend_cards.json")
    mpp_receipts = load_json(out / "mpp_receipts.json")

    for lead in outbound["leads"]:
        assert lead.get("requires_human_approval") is True
        drafts = lead.get("message_drafts", {})
        assert drafts, "Each lead should include outbound drafts"

    for request in creators["spend_requests"]:
        assert request.get("approval_status") == "pending"
        assert request.get("requires_approval") is True
        assert request.get("stripe_mode") in {"test", "demo"}
        assert 15 <= request.get("amount_usd", 0) <= 300

    for card in mpp_cards["spend_cards"]:
        assert card["protocol"] == "stripe_mpp"
        assert card["status"] == "awaiting_founder_approval"
        assert card["payment_challenge"]["http_status"] == 402
        assert card["payment_challenge"]["test_mode"] is True
        assert card["founder_guardrails"]["autonomous_spend_limit_usd"] == 0
        assert card["approval_command"].startswith("approve mpp_")

    assert {receipt["spend_card_id"] for receipt in mpp_receipts["receipts"]} == {card["id"] for card in mpp_cards["spend_cards"]}


def test_sprint_report_budget_numbers_come_from_profile(demo_run):
    """Regression: the report used to print a hardcoded $25 max single spend."""
    profile = load_json(demo_run["profile"])
    report = (demo_run["out"] / "weekly_flywheel_sprint.md").read_text(encoding="utf-8")
    assert f"${profile['budget']['max_single_spend_usd']}" in report
    assert f"${profile['budget']['weekly_usd']}" in report


def test_weekly_sprint_markdown_is_human_readable_and_complete(demo_run):
    report = (demo_run["out"] / "weekly_flywheel_sprint.md").read_text(encoding="utf-8")
    required_phrases = [
        "Weekly",
        "Executive Summary",
        "Launch",
        "Backlink",
        "Outbound",
        "Creator",
        "Spend",
        "Next Week",
        "Draft Review Dashboard",
        "help",
        "what can you do?",
        "review launch",
        "start walkthrough",
        "finalize sprint",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in report.lower()

    # The intake disclaimer must never leak into human-facing copy.
    assert "verify proof points before publishing" not in report.lower()


def test_outbound_copy_reads_naturally(demo_run):
    """Regression: proof points used to be spliced mid-sentence with broken grammar."""
    outbound_md = (demo_run["out"] / "outbound_queue.md").read_text(encoding="utf-8")
    assert "users reporting Turns store" not in outbound_md
    assert "verify proof points before publishing" not in outbound_md.lower()


def test_run_ledger_supports_slack_thread_demo(demo_run):
    ledger = load_json(demo_run["out"] / "runs" / "latest_run.json")
    assert ledger["thread_native_interface"]["primary_surface"] == "Slack or Telegram"
    assert ledger["thread_native_interface"]["quiet_callbacks"] is True
    assert ledger["status"] == "completed"
    assert any("weekly_flywheel_sprint.md" in artifact for artifact in ledger["artifacts"])
    assert "draft_review_dashboard" in ledger["thread_native_interface"]["human_thread_receives"]
    assert "help_message" in ledger["thread_native_interface"]["human_thread_receives"]
    assert {action["thread_command"] for action in ledger["approval_actions"]} >= {"help", "start walkthrough", "finalize sprint", "show approvals", "review launch"}


def test_validator_reports_success(demo_run):
    assert "All validations passed" in demo_run["stdout"]["validate_outputs.py"]


def test_validator_catches_planted_secret(demo_run, tmp_path):
    import shutil

    out = tmp_path / "seeded"
    shutil.copytree(demo_run["out"], out)
    target = out / "weekly_flywheel_sprint.md"
    target.write_text(
        target.read_text(encoding="utf-8")
        + '\napi_key = "sk-abcdefghijklmnopqrstuvwxyz123456"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_outputs.py"),
         "--profile", str(demo_run["profile"]),
         "--output-dir", str(out)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0
    assert "All validations passed" not in result.stdout


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

def test_sample_data_is_valid():
    profile = load_json(ROOT / "data/product_profile.example.json")
    assert profile["budget"]["requires_approval"] is True
    assert len(profile["competitors"]) >= 2

    with (ROOT / "data/leads.example.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 5
    assert {"name", "title", "company", "bio", "source", "url", "engagement_context"}.issubset(rows[0].keys())
