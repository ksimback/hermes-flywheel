#!/usr/bin/env python3
"""
Validation Script
Checks flywheel outputs for completeness, safety, and approval gates.
"""

import json
import os
from typing import Dict, List, Any, Tuple

def check_file_exists(path: str, description: str) -> Tuple[bool, str]:
    """Check if file exists and return status."""
    if os.path.exists(path):
        try:
            if path.endswith('.json'):
                with open(path, 'r') as f:
                    json.load(f)  # Validate JSON
            return True, f"✅ {description}"
        except json.JSONDecodeError:
            return False, f"❌ {description} - Invalid JSON"
        except Exception as e:
            return False, f"❌ {description} - Error: {e}"
    else:
        return False, f"❌ {description} - File not found"

def validate_product_profile(path: str = "data/product_profile.json") -> List[str]:
    """Validate product profile completeness."""
    issues = []

    try:
        with open(path, 'r') as f:
            profile = json.load(f)

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

def validate_launch_plan(path: str = "demo/demo-output/launch_plan.json") -> List[str]:
    """Validate launch plan completeness and safety."""
    issues = []

    try:
        with open(path, 'r') as f:
            plan = json.load(f)

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

def validate_backlink_opportunities(path: str = "demo/demo-output/backlink_opportunities.json") -> List[str]:
    """Validate backlink opportunities completeness and safety."""
    issues = []

    try:
        with open(path, 'r') as f:
            data = json.load(f)

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

def validate_outbound_queue(path: str = "demo/demo-output/outbound_queue.json") -> List[str]:
    """Validate outbound queue safety and completeness."""
    issues = []

    try:
        with open(path, 'r') as f:
            data = json.load(f)

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

def validate_creator_campaign(path: str = "demo/demo-output/creator_campaign.json") -> List[str]:
    """Validate creator campaign spend safety and completeness."""
    issues = []

    try:
        with open(path, 'r') as f:
            data = json.load(f)

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

def validate_mpp_spend_cards(path: str = "demo/demo-output/mpp_spend_cards.json", receipts_path: str = "demo/demo-output/mpp_receipts.json") -> List[str]:
    """Validate Stripe MPP spend cards and demo receipts."""
    issues = []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        with open(receipts_path, "r") as f:
            receipts_data = json.load(f)

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
            if card.get("protocol") != "stripe_mpp":
                issues.append(f"MPP spend card {card.get('id')} should use stripe_mpp protocol")
            if card.get("status") != "awaiting_founder_approval":
                issues.append(f"MPP spend card {card.get('id')} should await founder approval")
            if card.get("founder_guardrails", {}).get("autonomous_spend_limit_usd") != 0:
                issues.append(f"MPP spend card {card.get('id')} should keep autonomous spend at $0")
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
    except FileNotFoundError:
        issues.append("MPP spend card or receipt file not found")
    except json.JSONDecodeError:
        issues.append("MPP spend card or receipt file is not valid JSON")
    except Exception as e:
        issues.append(f"Error validating MPP spend cards: {e}")
    return issues


def validate_trend_content(path: str = "demo/demo-output/trend_content.json") -> List[str]:
    """Validate trend content safety and completeness."""
    issues = []

    try:
        with open(path, 'r') as f:
            data = json.load(f)

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

def validate_sprint_report(path: str = "demo/demo-output/weekly_flywheel_sprint.json") -> List[str]:
    """Validate final sprint report completeness."""
    issues = []

    try:
        with open(path, 'r') as f:
            report = json.load(f)

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

def check_safety_compliance() -> List[str]:
    """Check overall safety compliance across all outputs."""
    safety_issues = []

    # Check for secrets in markdown files
    md_files = [
        "demo/demo-output/launch_plan.md",
        "demo/demo-output/backlink_opportunities.md",
        "demo/demo-output/outbound_queue.md",
        "demo/demo-output/creator_campaign.md",
        "demo/demo-output/mpp_spend_cards.md",
        "demo/demo-output/trend_content.md",
        "demo/demo-output/weekly_flywheel_sprint.md"
    ]

    secret_patterns = ["api_key", "secret_key", "token", "password", "authorization:"]

    for md_file in md_files:
        if os.path.exists(md_file):
            try:
                with open(md_file, 'r') as f:
                    content = f.read().lower()
                    for pattern in secret_patterns:
                        if pattern in content and "example" not in content:
                            safety_issues.append(f"Potential secret in {md_file}: {pattern}")
            except Exception:
                pass  # Skip if can't read file

    # Check directory structure
    required_dirs = [
        "data",
        "demo/demo-output",
        "skills/flywheel-agent/scripts"
    ]

    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            safety_issues.append(f"Missing required directory: {dir_path}")

    return safety_issues

def main():
    """Main validation workflow."""
    print("🔍 Flywheel Agent - Output Validator")
    print("Checking completeness, safety, and approval gates...\n")

    all_issues = []
    validation_results = []

    # File existence checks
    file_checks = [
        ("data/product_profile.json", "Product Profile"),
        ("demo/demo-output/launch_plan.json", "Launch Plan"),
        ("demo/demo-output/backlink_opportunities.json", "Backlink Opportunities"),
        ("demo/demo-output/outbound_queue.json", "Outbound Queue"),
        ("demo/demo-output/creator_campaign.json", "Creator Campaign"),
        ("demo/demo-output/mpp_spend_cards.json", "Stripe MPP Spend Cards"),
        ("demo/demo-output/mpp_receipts.json", "Stripe MPP Receipts"),
        ("demo/demo-output/trend_content.json", "Trend Content"),
        ("demo/demo-output/weekly_flywheel_sprint.json", "Sprint Report")
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
        ("Product Profile", validate_product_profile),
        ("Launch Plan", validate_launch_plan),
        ("Backlink Opportunities", validate_backlink_opportunities),
        ("Outbound Queue", validate_outbound_queue),
        ("Creator Campaign", validate_creator_campaign),
        ("Stripe MPP Spend Cards", validate_mpp_spend_cards),
        ("Trend Content", validate_trend_content),
        ("Sprint Report", validate_sprint_report)
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
    safety_issues = check_safety_compliance()
    if safety_issues:
        print(f"   ❌ Safety: {len(safety_issues)} issues")
        all_issues.extend([f"Safety: {issue}" for issue in safety_issues])
    else:
        print("   ✅ Safety: Compliant")

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

        return 1
    else:
        print(f"\n✅ All validations passed!")
        print("   - All required files exist and are valid JSON")
        print("   - Content meets completeness requirements")
        print("   - Safety gates are properly configured")
        print("   - Approval requirements are enforced")
        print("   - No secrets detected in outputs")

        print(f"\n🚀 Flywheel Agent is ready for demo!")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())