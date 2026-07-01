import csv
import json
import os
import subprocess
import sys
from pathlib import Path

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

PIPELINE = [
    ("flywheel_intake.py", "--demo"),
    ("launch_plan.py",),
    ("backlink_hunter.py",),
    ("lead_scorer.py",),
    ("creator_campaign.py",),
    ("mpp_spend_planner.py",),
    ("trend_scan.py",),
    ("sprint_report.py",),
    ("validate_outputs.py",),
]


def run(cmd):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )


def load_json(relative_path):
    with (ROOT / relative_path).open() as f:
        return json.load(f)


def test_distribution_file_completeness():
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    missing += [f"skills/flywheel-agent/scripts/{name}" for name in REQUIRED_SCRIPTS if not (SCRIPTS / name).exists()]
    assert missing == []


def test_distribution_manifest_and_readme_install_path():
    manifest = (ROOT / "distribution.yaml").read_text()
    assert "name: flywheel-agent" in manifest
    assert "hermes_requires" in manifest
    assert "NVIDIA_API_KEY" in manifest
    assert "STRIPE_API_KEY" in manifest

    readme = (ROOT / "README.md").read_text()
    assert "hermes profile install" in readme
    assert "hermes profile install github.com/ksimback/hermes-flywheel --alias --yes" in readme
    assert "--alias flywheel-agent" not in readme
    assert "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash" in readme
    assert "hermes -p flywheel-agent setup --portal" in readme
    assert "flywheel-agent chat" in readme
    assert "installable Hermes Agent profile" in readme
    assert "Slack and Telegram" in readme
    assert "help" in readme
    assert "docs/slack-gtm-employee.md" in readme


    soul = (ROOT / "SOUL.md").read_text()
    skill = (ROOT / "skills/flywheel-agent/SKILL.md").read_text()
    public_prompt_text = soul + "\n" + skill
    forbidden_terms = [
        "Orbit" + "Kit",
        "Forge" + "AI",
        "Space" + "Tech",
        "Rocket" + " Labs",
    ]
    for term in forbidden_terms:
        assert term not in public_prompt_text

    required_demo_guardrails = [
        "Never mention fixture names",
        "Do not mention demo mode",
        "Do not mention old example products",
        "Never expose internal implementation notes",
    ]
    for phrase in required_demo_guardrails:
        assert phrase in public_prompt_text


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

    readme = (ROOT / "README.md").read_text().lower()
    assert "hermesflywheel.com" in readme
    assert "request" + "-access" not in readme
    assert "ver" + "cel" not in readme


def test_public_install_docs_are_focused_on_profile_distribution():
    readme = (ROOT / "README.md").read_text()
    manifest = (ROOT / "distribution.yaml").read_text()
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

    gitignore = (ROOT / ".gitignore").read_text()
    for pattern in [".env", "auth.json", "memories/", "sessions/", "state.db"]:
        assert pattern in gitignore


def test_python_scripts_compile():
    run([sys.executable, "-m", "compileall", "-q", "skills/flywheel-agent/scripts"])


def test_full_demo_pipeline_runs_without_paid_keys():
    for step in PIPELINE:
        script, *args = step
        result = run([sys.executable, str(SCRIPTS / script), *args])
        assert "Traceback" not in result.stdout


def test_intake_refuses_silent_fixture_without_input():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "flywheel_intake.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0
    assert "No product context provided" in result.stdout
    assert "--demo" in result.stdout


def test_intake_uses_real_founder_context():
    result = run([
        sys.executable,
        str(SCRIPTS / "flywheel_intake.py"),
        "Product: ExampleAI (https://example.ai) ICP: e-commerce founders Competitors: cartpilot.example Budget: $50 Focus: ExampleAI launch awareness",
        "--output",
        "demo/demo-output/test_exampleai_profile.json",
    ])
    assert "Using founder-provided product context" in result.stdout
    profile = load_json("demo/demo-output/test_exampleai_profile.json")
    assert profile["product_name"] == "ExampleAI"
    assert profile["url"] == "https://example.ai"
    assert profile["demo_mode"] is False
    assert "Orbit" + "Kit" not in json.dumps(profile)
    assert "Forge" + "AI" not in json.dumps(profile)


def test_generated_outputs_meet_acceptance_criteria():
    launch = load_json("demo/demo-output/launch_plan.json")
    backlinks = load_json("demo/demo-output/backlink_opportunities.json")
    outbound = load_json("demo/demo-output/outbound_queue.json")
    creators = load_json("demo/demo-output/creator_campaign.json")
    mpp_cards = load_json("demo/demo-output/mpp_spend_cards.json")
    mpp_receipts = load_json("demo/demo-output/mpp_receipts.json")
    trends = load_json("demo/demo-output/trend_content.json")
    sprint = load_json("demo/demo-output/weekly_flywheel_sprint.json")

    assert len(launch["launch_channels"]) >= 6
    assert backlinks["total_opportunities"] >= 10
    assert outbound["total_leads"] >= 10
    assert creators["total_proposals"] >= 1
    assert mpp_cards["protocol"] == "stripe_mpp"
    assert mpp_cards["total_spend_cards"] >= 3
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


def test_outbound_and_spend_are_approval_gated():
    outbound = load_json("demo/demo-output/outbound_queue.json")
    creators = load_json("demo/demo-output/creator_campaign.json")
    mpp_cards = load_json("demo/demo-output/mpp_spend_cards.json")
    mpp_receipts = load_json("demo/demo-output/mpp_receipts.json")

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


def test_weekly_sprint_markdown_is_human_readable_and_complete():
    report = (ROOT / "demo/demo-output/weekly_flywheel_sprint.md").read_text()
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


def test_sample_data_is_valid():
    profile = load_json("data/product_profile.example.json")
    assert profile["budget"]["requires_approval"] is True
    assert len(profile["competitors"]) >= 2

    with (ROOT / "data/leads.example.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 5
    assert {"name", "title", "company", "bio", "source", "url", "engagement_context"}.issubset(rows[0].keys())


def test_run_ledger_supports_slack_thread_demo():
    ledger = load_json("demo/demo-output/runs/latest_run.json")
    assert ledger["thread_native_interface"]["primary_surface"] == "Slack or Telegram"
    assert ledger["thread_native_interface"]["quiet_callbacks"] is True
    assert ledger["status"] == "completed"
    assert "demo/demo-output/weekly_flywheel_sprint.md" in ledger["artifacts"]
    assert "draft_review_dashboard" in ledger["thread_native_interface"]["human_thread_receives"]
    assert "help_message" in ledger["thread_native_interface"]["human_thread_receives"]
    assert {action["thread_command"] for action in ledger["approval_actions"]} >= {"help", "start walkthrough", "finalize sprint", "show approvals", "review launch"}


def test_validator_reports_success():
    result = run([sys.executable, str(SCRIPTS / "validate_outputs.py")])
    assert "All validations passed" in result.stdout
