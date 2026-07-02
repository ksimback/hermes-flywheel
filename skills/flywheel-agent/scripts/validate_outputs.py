#!/usr/bin/env python3
"""
Validation Script
Checks flywheel outputs for completeness, safety, and approval gates.

Compatibility note: newer generators stamp artifacts with "simulated" and
"data_source" fields. Those markers are validated when present, but their
absence only produces a warning so older committed artifacts still pass.
"""

import json
import math
import re
import traceback
from typing import Any, Dict, List, Tuple

from _common import (
    EXIT_ERROR,
    EXIT_OK,
    anchor,
    build_parser,
    configure_stdout,
    out_path,
)

# Credential-shaped patterns, scanned line by line. Fixture domains such as
# example.com must never suppress detection.
SECRET_PATTERNS = [
    # Hyphenated segments (sk-proj-..., sk-ant-api03-...) must still match.
    ("openai-style key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("slack token", re.compile(r"xox[abeprs]-[A-Za-z0-9\-]{10,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # Quote optional so unquoted env-style assignments are caught too.
    ("generic credential assignment", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
]


def read_json_file(path) -> Dict[str, Any]:
    with anchor(path).open(encoding="utf-8") as f:
        return json.load(f)


def check_file_exists(path, description: str) -> Tuple[bool, str]:
    """Check if file exists and return status."""
    path = anchor(path)
    if path.exists():
        try:
            if path.suffix == ".json":
                read_json_file(path)  # Validate JSON
            return True, f"✅ {description}"
        except json.JSONDecodeError:
            return False, f"❌ {description} - Invalid JSON"
        except Exception as e:
            return False, f"❌ {description} - Error: {e}"
    else:
        return False, f"❌ {description} - File not found"


def check_simulated_marker(payload: Dict[str, Any], label: str, warnings: List[str]) -> List[str]:
    """Require simulated=true when the marker is present; warn when absent.

    Older committed artifacts predate the "simulated" honesty marker, so a
    missing field is warn-only. A present-but-untrue value is a hard failure.
    """
    issues = []
    if "simulated" in payload:
        if payload.get("simulated") is not True:
            issues.append(f"{label} sets 'simulated' but not to true - simulated artifacts must be honest")
    else:
        warnings.append(f"{label} missing 'simulated': true marker (old-format artifact - regenerate to add it)")
    # "data_source" is an accepted informational field; nothing to enforce.
    return issues


def validate_product_profile(path) -> List[str]:
    """Validate product profile completeness."""
    issues = []

    try:
        profile = read_json_file(path)

        required_fields = [
            "product_name", "url", "one_liner", "category",
            "icp", "competitors", "positioning", "budget"
        ]

        for field in required_fields:
            if field not in profile:
                issues.append(f"Missing required field: {field}")

        # Validate budget structure
        if "budget" in profile:
            budget = profile["budget"]
            if "weekly_usd" not in budget or budget.get("weekly_usd", 0) <= 0:
                issues.append("Budget missing valid weekly_usd")
            if "max_single_spend_usd" not in budget or budget.get("max_single_spend_usd", 0) <= 0:
                issues.append("Budget missing valid max_single_spend_usd")
            if not budget.get("requires_approval", True):
                issues.append("Budget should require approval by default")

        # Validate ICP structure
        if "icp" in profile:
            icp = profile["icp"]
            if not icp.get("buyer"):
                issues.append("ICP missing buyer definition")
            if not icp.get("pain_points") or len(icp["pain_points"]) == 0:
                issues.append("ICP missing pain points")

        # Validate competitors
        if "competitors" in profile and len(profile["competitors"]) < 2:
            issues.append("Should have at least 2 competitors for analysis")

    except FileNotFoundError:
        issues.append("Product profile file not found")
    except json.JSONDecodeError:
        issues.append("Product profile is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating product profile: {e}")

    return issues


def validate_launch_plan(path) -> List[str]:
    """Validate launch plan completeness and safety."""
    issues = []

    try:
        plan = read_json_file(path)

        channels = plan.get("launch_channels", [])
        if len(channels) < 6:
            issues.append(f"Expected at least 6 launch channels, found {len(channels)}")

        for channel in channels:
            # Check required fields
            required = ["channel", "name", "copy", "approval_required", "priority_score"]
            for field in required:
                if field not in channel:
                    issues.append(f"Launch channel {channel.get('name', 'unknown')} missing {field}")

            # Check approval requirement
            if not channel.get("approval_required", False):
                issues.append(f"Launch channel {channel.get('name')} should require approval")

        # Check asset requirements
        if not plan.get("asset_requirements") or len(plan["asset_requirements"]) == 0:
            issues.append("Launch plan should include asset requirements")

    except FileNotFoundError:
        issues.append("Launch plan file not found")
    except json.JSONDecodeError:
        issues.append("Launch plan is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating launch plan: {e}")

    return issues


def validate_backlink_opportunities(path) -> List[str]:
    """Validate backlink opportunities completeness and safety."""
    issues = []

    try:
        data = read_json_file(path)

        opportunities = data.get("opportunities", [])
        if len(opportunities) < 5:
            issues.append(f"Expected at least 5 opportunities, found {len(opportunities)}")

        for opp in opportunities:
            # Check required fields
            required = ["id", "type", "source_url", "title", "score", "approval_required"]
            for field in required:
                if field not in opp:
                    issues.append(f"Opportunity {opp.get('id', 'unknown')} missing {field}")

            # Check approval requirement
            if not opp.get("approval_required", False):
                issues.append(f"Opportunity {opp.get('id')} should require approval")

            # Check outreach template exists
            if not opp.get("outreach_template"):
                issues.append(f"Opportunity {opp.get('id')} missing outreach template")

    except FileNotFoundError:
        issues.append("Backlink opportunities file not found")
    except json.JSONDecodeError:
        issues.append("Backlink opportunities is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating backlink opportunities: {e}")

    return issues


def validate_outbound_queue(path) -> List[str]:
    """Validate outbound queue safety and completeness."""
    issues = []

    try:
        data = read_json_file(path)

        leads = data.get("leads", [])
        if len(leads) == 0:
            issues.append("No leads found in outbound queue")

        for lead in leads:
            # Check required fields
            required = ["name", "icp_fit_score", "personalized_message", "approval_required"]
            for field in required:
                if field not in lead:
                    issues.append(f"Lead {lead.get('name', 'unknown')} missing {field}")

            # Check approval requirement (CRITICAL)
            if not lead.get("approval_required", False):
                issues.append(f"CRITICAL: Lead {lead.get('name')} missing approval requirement")

            # Check message quality
            message = lead.get("personalized_message", "")
            if len(message) < 50:
                issues.append(f"Lead {lead.get('name')} message too short (< 50 chars)")
            if "[Your name]" not in message and "[Name]" not in message:
                issues.append(f"Lead {lead.get('name')} message missing sender placeholder")

    except FileNotFoundError:
        issues.append("Outbound queue file not found")
    except json.JSONDecodeError:
        issues.append("Outbound queue is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating outbound queue: {e}")

    return issues


def validate_creator_campaign(path) -> List[str]:
    """Validate creator campaign spend safety and completeness."""
    issues = []

    try:
        data = read_json_file(path)

        proposals = data.get("campaign_proposals", [])
        spend_requests = data.get("spend_requests", [])

        if len(proposals) == 0:
            issues.append("No creator campaign proposals found")

        for proposal in proposals:
            # Check approval requirement
            if not proposal.get("approval_required", False):
                issues.append(f"Creator {proposal.get('creator', 'unknown')} proposal should require approval")

            # Check pricing structure
            pricing = proposal.get("pricing", {})
            if not pricing.get("base_fee") or not pricing.get("performance_bonus"):
                issues.append(f"Creator {proposal.get('creator')} missing complete pricing structure")

        # Validate spend requests (CRITICAL for safety)
        for req in spend_requests:
            required = ["amount_usd", "purpose", "approval_status", "requires_approval"]
            for field in required:
                if field not in req:
                    issues.append(f"CRITICAL: Spend request {req.get('id', 'unknown')} missing {field}")

            # Check approval status
            if req.get("approval_status") != "pending":
                issues.append(f"CRITICAL: Spend request {req.get('id')} should be pending approval")

            if not req.get("requires_approval", False):
                issues.append(f"CRITICAL: Spend request {req.get('id')} should require approval")

            # Check test mode
            if req.get("stripe_mode") != "test":
                issues.append(f"WARNING: Spend request {req.get('id')} should use test mode")

    except FileNotFoundError:
        issues.append("Creator campaign file not found")
    except json.JSONDecodeError:
        issues.append("Creator campaign is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating creator campaign: {e}")

    return issues


def validate_mpp_spend_cards(path, receipts_path, warnings: List[str], max_single_spend_usd=0) -> List[str]:
    """Validate Stripe MPP spend cards and simulated receipts."""
    issues = []
    try:
        data = read_json_file(path)
        receipts_data = read_json_file(receipts_path)

        # Simulated-honesty markers (warn-only when absent, required-true when present)
        issues.extend(check_simulated_marker(data, "MPP spend cards file", warnings))
        issues.extend(check_simulated_marker(receipts_data, "MPP receipts file", warnings))

        cards = data.get("spend_cards", [])
        receipts = receipts_data.get("receipts", [])
        if len(cards) < 3:
            issues.append(f"Expected at least 3 MPP spend cards, found {len(cards)}")
        if len(receipts) != len(cards):
            issues.append("MPP receipt count should match spend card count")

        receipt_card_ids = {receipt.get("spend_card_id") for receipt in receipts}
        for card in cards:
            required = ["id", "protocol", "status", "approval_command", "payment_challenge", "founder_guardrails", "chat_card"]
            for field in required:
                if field not in card:
                    issues.append(f"MPP spend card {card.get('id', 'unknown')} missing {field}")
            # Amount sanity: a spend card must carry a positive finite amount.
            amount = card.get("amount_usd")
            if (not isinstance(amount, (int, float)) or isinstance(amount, bool)
                    or not math.isfinite(amount) or amount <= 0):
                issues.append(f"MPP spend card {card.get('id', 'unknown')} amount_usd must be a positive finite number, got {amount!r}")
            elif max_single_spend_usd and amount > max_single_spend_usd:
                warnings.append(
                    f"MPP spend card {card.get('id', 'unknown')} amount ${amount} exceeds "
                    f"profile max_single_spend_usd ${max_single_spend_usd}"
                )
            if card.get("protocol") != "stripe_mpp":
                issues.append(f"MPP spend card {card.get('id')} should use stripe_mpp protocol")
            if card.get("status") != "awaiting_founder_approval":
                issues.append(f"MPP spend card {card.get('id')} should await founder approval")
            if card.get("founder_guardrails", {}).get("autonomous_spend_limit_usd") != 0:
                issues.append(f"MPP spend card {card.get('id')} should keep autonomous spend at $0")
            if not card.get("founder_guardrails", {}).get("requires_human_approval", False):
                issues.append(f"MPP spend card {card.get('id')} should require human approval")
            if not str(card.get("approval_command", "")).startswith("approve mpp_"):
                issues.append(f"MPP spend card {card.get('id')} missing 'approve mpp_' approval command")
            challenge = card.get("payment_challenge", {})
            if challenge.get("http_status") != 402 or challenge.get("test_mode") is not True:
                issues.append(f"MPP spend card {card.get('id')} should include test-mode 402 challenge")
            if card.get("id") not in receipt_card_ids:
                issues.append(f"MPP spend card {card.get('id')} missing receipt")

        for receipt in receipts:
            if receipt.get("protocol") != "stripe_mpp" or receipt.get("mode") != "test":
                issues.append(f"Receipt {receipt.get('receipt_id', 'unknown')} should be test-mode stripe_mpp")
            if not receipt.get("payment_intent", "").startswith("pi_test_mpp_"):
                issues.append(f"Receipt {receipt.get('receipt_id', 'unknown')} missing test payment intent")
            issues.extend(check_simulated_marker(receipt, f"Receipt {receipt.get('receipt_id', 'unknown')}", warnings))
    except FileNotFoundError:
        issues.append("MPP spend card or receipt file not found")
    except json.JSONDecodeError:
        issues.append("MPP spend card or receipt file is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating MPP spend cards: {e}")
    return issues


def validate_trend_content(path) -> List[str]:
    """Validate trend content safety and completeness."""
    issues = []

    try:
        data = read_json_file(path)

        content_drafts = data.get("content_drafts", [])
        if len(content_drafts) == 0:
            issues.append("No trend content drafts found")

        for draft in content_drafts:
            # Check approval requirement
            if not draft.get("approval_required", False):
                issues.append(f"Content draft {draft.get('format', 'unknown')} should require approval")

            # Check content exists
            if not draft.get("content") or len(draft["content"]) < 50:
                issues.append(f"Content draft {draft.get('format')} missing or too short")

            # Check posting guidelines
            if not draft.get("posting_guidelines"):
                issues.append(f"Content draft {draft.get('format')} missing posting guidelines")

    except FileNotFoundError:
        issues.append("Trend content file not found")
    except json.JSONDecodeError:
        issues.append("Trend content is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating trend content: {e}")

    return issues


def validate_sprint_report(path) -> List[str]:
    """Validate final sprint report completeness."""
    issues = []

    try:
        report = read_json_file(path)

        summary = report.get("sprint_summary", {})

        # Check key metrics
        if summary.get("total_actions", 0) == 0:
            issues.append("Sprint report shows 0 total actions")

        # Check approval gates
        approval_gates = summary.get("approval_gates", {})
        if approval_gates.get("outbound_messages", 0) == 0 and approval_gates.get("content_posts", 0) == 0:
            issues.append("Sprint report should show approval requirements")

        # Check budget analysis
        budget_analysis = summary.get("budget_analysis", {})
        if not budget_analysis.get("weekly_budget"):
            issues.append("Sprint report missing budget analysis")

        # Check next week plan
        next_week = report.get("next_week_plan", {})
        if not next_week.get("focus_areas") or len(next_week["focus_areas"]) == 0:
            issues.append("Sprint report missing next week focus areas")

    except FileNotFoundError:
        issues.append("Sprint report file not found")
    except json.JSONDecodeError:
        issues.append("Sprint report is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating sprint report: {e}")

    return issues


def scan_file_for_secrets(path) -> List[str]:
    """Scan one file line by line for credential-shaped strings."""
    findings = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        findings.append(f"Could not scan {path.name} for secrets: {e}")
        return findings
    for line_no, line in enumerate(content.splitlines(), 1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"Potential secret ({label}) in {path.name}:{line_no}")
    return findings


def check_safety_compliance(args) -> List[str]:
    """Check overall safety compliance across all outputs."""
    safety_issues = []

    # Scan every markdown and JSON artifact in the output dir (including the
    # run ledgers) plus the profile itself for credential shapes.
    # Fixture domains (example.com etc.) do NOT suppress detection.
    output_dir = anchor(args.output_dir)
    if output_dir.exists():
        scan_targets = (
            sorted(output_dir.glob("*.md"))
            + sorted(output_dir.glob("*.json"))
            + sorted(output_dir.glob("runs/*.json"))
        )
        for artifact in scan_targets:
            safety_issues.extend(scan_file_for_secrets(artifact))

    profile_path = anchor(args.profile)
    if profile_path.exists():
        safety_issues.extend(scan_file_for_secrets(profile_path))

    # Check directory structure
    required_dirs = [
        anchor("data"),
        output_dir,
        anchor("skills/flywheel-agent/scripts"),
    ]

    for dir_path in required_dirs:
        if not dir_path.exists():
            safety_issues.append(f"Missing required directory: {dir_path}")

    return safety_issues


def run_validations(args) -> int:
    """Run the full validation workflow, return an exit code."""
    all_issues = []
    # Warn-only findings (e.g. old-format artifacts missing new markers).
    # Threaded through explicitly so repeated runs stay re-entrant.
    warnings: List[str] = []

    profile_path = anchor(args.profile)

    # Profile-derived guardrails used by artifact sanity checks.
    max_single_spend_usd = 0
    try:
        profile_budget = read_json_file(profile_path).get("budget", {}) or {}
        if isinstance(profile_budget.get("max_single_spend_usd"), (int, float)):
            max_single_spend_usd = profile_budget["max_single_spend_usd"]
    except Exception:
        pass  # Missing/invalid profile is reported by the checks below.

    # File existence checks
    file_checks = [
        (profile_path, "Product Profile"),
        (out_path(args, "launch_plan.json"), "Launch Plan"),
        (out_path(args, "backlink_opportunities.json"), "Backlink Opportunities"),
        (out_path(args, "outbound_queue.json"), "Outbound Queue"),
        (out_path(args, "creator_campaign.json"), "Creator Campaign"),
        (out_path(args, "mpp_spend_cards.json"), "Stripe MPP Spend Cards"),
        (out_path(args, "mpp_receipts.json"), "Stripe MPP Receipts"),
        (out_path(args, "trend_content.json"), "Trend Content"),
        (out_path(args, "weekly_flywheel_sprint.json"), "Sprint Report")
    ]

    print("📁 File Existence Check:")
    for path, description in file_checks:
        exists, status = check_file_exists(path, description)
        print(f"   {status}")
        if not exists:
            all_issues.append(f"Missing file: {path}")

    print("\n🔍 Content Validation:")

    # Content validation
    validations = [
        ("Product Profile", lambda: validate_product_profile(profile_path)),
        ("Launch Plan", lambda: validate_launch_plan(out_path(args, "launch_plan.json"))),
        ("Backlink Opportunities", lambda: validate_backlink_opportunities(out_path(args, "backlink_opportunities.json"))),
        ("Outbound Queue", lambda: validate_outbound_queue(out_path(args, "outbound_queue.json"))),
        ("Creator Campaign", lambda: validate_creator_campaign(out_path(args, "creator_campaign.json"))),
        ("Stripe MPP Spend Cards", lambda: validate_mpp_spend_cards(
            out_path(args, "mpp_spend_cards.json"), out_path(args, "mpp_receipts.json"),
            warnings, max_single_spend_usd)),
        ("Trend Content", lambda: validate_trend_content(out_path(args, "trend_content.json"))),
        ("Sprint Report", lambda: validate_sprint_report(out_path(args, "weekly_flywheel_sprint.json")))
    ]

    for name, validator in validations:
        try:
            issues = validator()
            if issues:
                print(f"   ❌ {name}: {len(issues)} issues")
                all_issues.extend([f"{name}: {issue}" for issue in issues])
            else:
                print(f"   ✅ {name}: Valid")
        except Exception as e:
            print(f"   ❌ {name}: Validation failed - {e}")
            all_issues.append(f"{name}: Validation failed - {e}")

    # Safety compliance check
    print("\n🔒 Safety Compliance Check:")
    safety_issues = check_safety_compliance(args)
    if safety_issues:
        print(f"   ❌ Safety: {len(safety_issues)} issues")
        all_issues.extend([f"Safety: {issue}" for issue in safety_issues])
    else:
        print("   ✅ Safety: Compliant")

    # Warn-only findings (never fail the run)
    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}, non-blocking):")
        for i, warning in enumerate(warnings, 1):
            print(f"   {i}. {warning}")

    # Summary
    print(f"\n📊 Validation Summary:")
    print(f"   Total Issues: {len(all_issues)}")

    if all_issues:
        print(f"\n❌ Validation Issues Found:")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i}. {issue}")

        print(f"\n🔧 Recommended Fixes:")
        print("   1. Run missing scripts to generate required files")
        print("   2. Check approval_required flags are set to true")
        print("   3. Verify no secrets are included in output files")
        print("   4. Ensure all spend requests are in test mode")

        return EXIT_ERROR
    else:
        print(f"\n✅ All validations passed!")
        print("   - All required files exist and are valid JSON")
        print("   - Content meets completeness requirements")
        print("   - Safety gates are properly configured")
        print("   - Approval requirements are enforced")
        print("   - No secrets detected in outputs")

        print(f"\n🚀 Flywheel Agent is ready for demo!")
        return EXIT_OK


def main():
    """Main validation workflow."""
    configure_stdout()
    print("🔍 Flywheel Agent - Output Validator")
    print("Checking completeness, safety, and approval gates...\n")

    parser = build_parser("Validate flywheel outputs for completeness, safety, and approval gates.", research=False)
    args = parser.parse_args()

    try:
        return run_validations(args)
    except Exception as e:
        traceback.print_exc()
        print(f"❌ Validation run failed: {e}")
        return EXIT_ERROR


if __name__ == "__main__":
    import sys
    sys.exit(main())
