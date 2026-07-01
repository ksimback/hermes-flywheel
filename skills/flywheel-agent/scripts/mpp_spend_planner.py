#!/usr/bin/env python3
"""
Stripe MPP Spend Planner
Builds deterministic MPP-style spend cards, payment challenges, and test receipts
for Flywheel's approval-gated GTM procurement loop.

This is a demo-safe protocol simulation: no live Stripe API calls are made and no
money moves. It models the handoff Flywheel would use with MPP-compatible paid
resources after a founder approves spend in Slack or Telegram.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

OUTPUT_DIR = "demo/demo-output"
SPEND_CARDS_PATH = f"{OUTPUT_DIR}/mpp_spend_cards.json"
RECEIPTS_PATH = f"{OUTPUT_DIR}/mpp_receipts.json"


def load_json_safely(path: str) -> Optional[Dict[str, Any]]:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as exc:
        print(f"Warning: could not load {path}: {exc}")
    return None


def dollars_to_cents(amount_usd: int) -> int:
    return int(amount_usd * 100)


def build_spend_card(
    *,
    card_id: str,
    resource_type: str,
    resource_name: str,
    provider: str,
    endpoint: str,
    amount_usd: int,
    reason: str,
    expected_outcome: str,
    source: str,
    weekly_budget: int,
) -> Dict[str, Any]:
    """Create a deterministic Stripe MPP spend card."""
    amount_cents = dollars_to_cents(amount_usd)
    return {
        "id": card_id,
        "protocol": "stripe_mpp",
        "status": "awaiting_founder_approval",
        "approval_command": f"approve {card_id}",
        "reject_command": f"reject {card_id}",
        "resource_type": resource_type,
        "resource_name": resource_name,
        "provider": provider,
        "http_endpoint": endpoint,
        "amount_usd": amount_usd,
        "amount_cents": amount_cents,
        "currency": "usd",
        "reason": reason,
        "expected_outcome": expected_outcome,
        "source_sprint_section": source,
        "payment_challenge": {
            "http_status": 402,
            "www_authenticate": "Payment",
            "method": "stripe.mpp.charge",
            "resource": endpoint,
            "amount_cents": amount_cents,
            "currency": "usd",
            "test_mode": True,
        },
        "founder_guardrails": {
            "weekly_budget_usd": weekly_budget,
            "requires_human_approval": True,
            "autonomous_spend_limit_usd": 0,
            "percentage_of_weekly_budget": round((amount_usd / weekly_budget) * 100, 1) if weekly_budget else 0,
        },
        "chat_card": {
            "title": f"MPP spend request: {resource_name}",
            "body": f"Pay ${amount_usd} via Stripe MPP for {reason}",
            "primary_action": f"approve {card_id}",
            "secondary_action": f"reject {card_id}",
        },
    }


def generate_mpp_spend_cards(profile: Dict[str, Any], all_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate A+B style GTM procurement spend cards."""
    weekly_budget = profile.get("budget", {}).get("weekly_usd", 500)
    cards: List[Dict[str, Any]] = []

    creator_requests = all_data.get("creator_campaign", {}).get("spend_requests", [])
    if creator_requests:
        top_creator = creator_requests[0]
        cards.append(build_spend_card(
            card_id="mpp_creator_001",
            resource_type="creator_test",
            resource_name=f"{top_creator.get('creator', 'Creator')} launch-week test",
            provider="Example Creator Market",
            endpoint="https://mpp.example.ai/resources/creator-test",
            amount_usd=int(top_creator.get("amount_usd", 75)),
            reason="unlock a creator test for the highest-scoring launch audience",
            expected_outcome=top_creator.get("expected_outcome", "creator brief and launch-week post"),
            source="creator_campaign",
            weekly_budget=weekly_budget,
        ))

    opportunities = all_data.get("backlink_opportunities", {}).get("opportunities", [])
    if opportunities:
        top_opp = opportunities[0]
        cards.append(build_spend_card(
            card_id="mpp_data_001",
            resource_type="competitor_demand_data",
            resource_name="Competitor demand data pull",
            provider="Example Demand Data API",
            endpoint="https://mpp.example.ai/resources/competitor-demand-report",
            amount_usd=12,
            reason=f"unlock source data behind {top_opp.get('title', 'the top competitor opportunity')[:60]}",
            expected_outcome="paid competitor placement paths, source URLs, and outreach priority scores",
            source="backlink_opportunities",
            weekly_budget=weekly_budget,
        ))

    launch_channels = all_data.get("launch_plan", {}).get("launch_channels", [])
    if launch_channels:
        top_channel = launch_channels[0]
        cards.append(build_spend_card(
            card_id="mpp_launch_001",
            resource_type="launch_placement",
            resource_name=f"{top_channel.get('name', 'Launch channel')} paid placement",
            provider="Example Launch Directory",
            endpoint="https://mpp.example.ai/resources/launch-placement",
            amount_usd=49,
            reason="reserve a paid launch placement after founder approves the channel angle",
            expected_outcome="launch placement slot, submission receipt, and tracking link",
            source="launch_plan",
            weekly_budget=weekly_budget,
        ))

    cards.append(build_spend_card(
        card_id="mpp_execution_001",
        resource_type="execution_infrastructure",
        resource_name="Browser execution session",
        provider="Example Browser Session Provider",
        endpoint="https://mpp.example.ai/resources/browser-session",
        amount_usd=1,
        reason="run a paid execution session for approved launch submission checks",
        expected_outcome="one browser automation session with receipt attached to the sprint ledger",
        source="execution_infrastructure",
        weekly_budget=weekly_budget,
    ))

    return cards


def build_demo_receipts(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create deterministic test receipts that show what returns after approval."""
    receipts = []
    for index, card in enumerate(cards, 1):
        receipts.append({
            "receipt_id": f"mpp_receipt_{index:03d}",
            "spend_card_id": card["id"],
            "protocol": "stripe_mpp",
            "mode": "test",
            "status": "simulated_after_founder_approval",
            "payment_intent": f"pi_test_mpp_{index:06d}",
            "stripe_receipt_url": f"https://dashboard.stripe.com/test/payments/pi_test_mpp_{index:06d}",
            "resource_unlocked": card["http_endpoint"],
            "amount_usd": card["amount_usd"],
            "currency": card["currency"],
            "ledger_note": "Demo receipt only. No live Stripe call and no money moved.",
        })
    return receipts


def save_outputs(cards: List[Dict[str, Any]], receipts: List[Dict[str, Any]]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now = datetime.now().isoformat()
    total = sum(card["amount_usd"] for card in cards)
    spend_payload = {
        "generated_at": now,
        "protocol": "stripe_mpp",
        "integration_story": "Flywheel uses Stripe MPP as the transaction layer for approved GTM procurement.",
        "workflow": [
            "Flywheel discovers a paid GTM resource.",
            "The provider returns an MPP-style 402 payment challenge.",
            "Flywheel turns it into a founder approval card in Slack or Telegram.",
            "After approval, Flywheel pays programmatically in test mode and unlocks the resource.",
            "The Stripe receipt returns to the sprint ledger.",
        ],
        "total_spend_cards": len(cards),
        "total_pending_amount_usd": total,
        "spend_cards": cards,
        "demo_mode": True,
    }
    receipt_payload = {
        "generated_at": now,
        "protocol": "stripe_mpp",
        "mode": "test",
        "total_receipts": len(receipts),
        "receipts": receipts,
        "demo_mode": True,
    }
    with open(SPEND_CARDS_PATH, "w") as f:
        json.dump(spend_payload, f, indent=2)
    with open(RECEIPTS_PATH, "w") as f:
        json.dump(receipt_payload, f, indent=2)
    save_markdown(spend_payload, receipt_payload)
    print(f"✓ MPP spend cards saved to {SPEND_CARDS_PATH}")
    print(f"✓ MPP receipts saved to {RECEIPTS_PATH}")


def save_markdown(spend_payload: Dict[str, Any], receipt_payload: Dict[str, Any]) -> None:
    cards = spend_payload["spend_cards"]
    receipts = receipt_payload["receipts"]
    md = f"""# Stripe MPP Spend Cards

Generated: {spend_payload['generated_at']}
Protocol: Stripe MPP
Demo mode: {spend_payload.get('demo_mode', False)}

Flywheel uses Stripe MPP as the transaction layer for approved GTM procurement. Paid resources become approval cards, payment stays locked until the founder approves, and test receipts return to the sprint ledger.

## MPP Workflow

"""
    for step in spend_payload["workflow"]:
        md += f"- {step}\n"
    md += "\n## Pending MPP Spend Cards\n\n| Card | Resource | Amount | Approval command | Expected outcome |\n|---|---|---:|---|---|\n"
    for card in cards:
        md += f"| `{card['id']}` | {card['resource_name']} | ${card['amount_usd']} | `{card['approval_command']}` | {card['expected_outcome']} |\n"
    md += "\n## Test Receipts After Approval\n\n| Receipt | Card | PaymentIntent | Resource unlocked |\n|---|---|---|---|\n"
    for receipt in receipts:
        md += f"| `{receipt['receipt_id']}` | `{receipt['spend_card_id']}` | `{receipt['payment_intent']}` | {receipt['resource_unlocked']} |\n"
    md += "\nNo live Stripe call is made in this deterministic demo.\n"
    with open(f"{OUTPUT_DIR}/mpp_spend_cards.md", "w") as f:
        f.write(md)


def main() -> int:
    print("💳 Flywheel Agent - Stripe MPP Spend Planner")
    profile = load_json_safely("data/product_profile.json")
    if not profile:
        print("Missing product profile. Run flywheel_intake.py first.")
        return 1
    all_data = {
        "launch_plan": load_json_safely("demo/demo-output/launch_plan.json") or {},
        "backlink_opportunities": load_json_safely("demo/demo-output/backlink_opportunities.json") or {},
        "creator_campaign": load_json_safely("demo/demo-output/creator_campaign.json") or {},
    }
    cards = generate_mpp_spend_cards(profile, all_data)
    receipts = build_demo_receipts(cards)
    save_outputs(cards, receipts)
    print(f"✓ Generated {len(cards)} MPP spend cards totaling ${sum(card['amount_usd'] for card in cards)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
