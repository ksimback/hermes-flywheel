#!/usr/bin/env python3
"""
Flywheel Intake Script
Converts founder input into structured product profile for GTM operations.

Default behavior is production-safe: it requires real product context from
stdin/CLI. Demo fixture data is available only with --demo so installed users
never accidentally get ExampleAI outputs for their own product.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional


def create_demo_profile() -> Dict[str, Any]:
    """Create the explicit demo product profile used by tests and recorded demos."""
    return {
        "product_name": "ExampleAI",
        "url": "https://example.ai",
        "one_liner": "E-commerce intelligence engine for growth teams",
        "description": "ExampleAI helps e-commerce founders understand store performance, customer segments, and growth opportunities from one lightweight intelligence layer.",
        "category": "e-commerce intelligence",
        "icp": {
            "buyer": "e-commerce founders",
            "company_stage": "pre-seed to series-a",
            "company_size": "1-50 employees",
            "pain_points": [
                "manual store analysis",
                "unclear customer segments",
                "slow competitor research",
                "spreadsheet-heavy growth planning"
            ],
            "keywords": ["e-commerce", "customer intelligence", "growth", "retention", "merchandising"]
        },
        "competitors": [
            "https://cartpilot.example",
            "https://shopflow.example",
            "https://growthdock.example"
        ],
        "positioning": {
            "primary_claim": "E-commerce intelligence for founders who need clearer growth decisions",
            "proof_points": [
                "Turns store and customer signals into weekly GTM actions",
                "Highlights audience segments and campaign opportunities",
                "Keeps outreach and spend approval-gated"
            ],
            "contra_positioning": [
                "not a storefront builder",
                "not a generic analytics dashboard",
                "not an ad network"
            ]
        },
        "budget": {
            "weekly_usd": 500,
            "max_single_spend_usd": 100,
            "requires_approval": True,
            "stripe_mode": "test"
        },
        "generated_at": datetime.now().isoformat(),
        "demo_mode": True,
        "fixture": "exampleai-demo"
    }


LABELS = [
    "product", "name", "url", "one_liner", "one-liner", "description", "what it does",
    "icp", "ideal customer", "customer", "audience", "competitors", "competition",
    "alternatives", "budget", "weekly budget", "spend", "focus", "goal", "priority",
    "category", "market", "niche"
]


def _value_for_label(raw_input: str, labels: List[str]) -> Optional[str]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    all_labels = "|".join(re.escape(label) for label in LABELS)
    match = re.search(
        rf"(?is)(?:^|\n|\s)(?:{label_pattern})\s*:\s*(.*?)(?=(?:\s+(?:{all_labels})\s*:)|$)",
        raw_input,
    )
    return match.group(1).strip(" \t\n.;") if match else None


def _split_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = re.split(r",|\n|;", value)
    return [p.strip(" \t-•") for p in parts if p.strip(" \t-•")]


def _extract_url(raw_input: str) -> str:
    match = re.search(r"https?://[^\s)]+", raw_input)
    if match:
        return match.group(0).rstrip(".,")
    domain = re.search(r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\b", raw_input, re.I)
    if domain:
        return f"https://{domain.group(0).rstrip('.,')}"
    return ""


def _extract_budget(raw_input: str) -> Dict[str, Any]:
    budget_text = _value_for_label(raw_input, ["budget", "weekly budget", "spend"])
    amount = None
    if budget_text:
        match = re.search(r"\$?\s*([0-9][0-9,]*)", budget_text)
        if match:
            amount = int(match.group(1).replace(",", ""))
    if amount is None:
        amount = 100
    return {
        "weekly_usd": amount,
        "max_single_spend_usd": max(10, min(100, amount // 4 if amount else 25)),
        "requires_approval": True,
        "stripe_mode": "test"
    }


def _extract_product_name(raw_input: str) -> str:
    labeled = _value_for_label(raw_input, ["product", "name"])
    if labeled:
        candidate = re.sub(r"\s*\([^)]*\)", "", labeled).strip()
        return candidate.split()[0].strip("@:,.") if candidate else "Product"
    for pattern in [
        r"(?i)for\s+([A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,2})",
    ]:
        match = re.search(pattern, raw_input)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"\s*\([^)]*\)", "", candidate).strip()
            if candidate:
                return candidate
    first_line = next((line.strip() for line in raw_input.splitlines() if line.strip()), "")
    return first_line.split()[0].strip("@:,.") if first_line else "Product"


def normalize_input(raw_input: str) -> Dict[str, Any]:
    """Normalize founder-provided product context into a structured profile."""
    raw_input = raw_input.strip()
    if not raw_input:
        raise ValueError("No product context provided. Pass product details via stdin/argument, or use --demo for the ExampleAI fixture.")

    product_name = _extract_product_name(raw_input)
    url = _extract_url(raw_input)
    icp_text = _value_for_label(raw_input, ["icp", "ideal customer", "customer", "audience"]) or "early-stage founders and growth operators"
    competitors = _split_list(_value_for_label(raw_input, ["competitors", "competition", "alternatives"]))
    focus = _value_for_label(raw_input, ["focus", "goal", "priority"]) or "customer acquisition"
    one_liner = _value_for_label(raw_input, ["one_liner", "one-liner", "description", "what it does"]) or f"{product_name} helps {icp_text} with {focus}"
    category = _value_for_label(raw_input, ["category", "market", "niche"]) or "software"

    keywords = [word.strip().lower() for word in re.split(r"\W+", f"{icp_text} {focus} {category}") if len(word.strip()) > 3][:8]
    if not competitors:
        competitors = []

    return {
        "product_name": product_name,
        "url": url,
        "one_liner": one_liner,
        "description": raw_input,
        "category": category,
        "icp": {
            "buyer": icp_text,
            "company_stage": "unknown",
            "company_size": "unknown",
            "pain_points": [focus],
            "keywords": keywords or ["growth", "acquisition"]
        },
        "competitors": competitors,
        "positioning": {
            "primary_claim": one_liner,
            "proof_points": [
                "Founder-provided context; verify proof points before publishing",
                "Use live research to sharpen differentiation",
                "Keep claims conservative until validated"
            ],
            "contra_positioning": []
        },
        "budget": _extract_budget(raw_input),
        "generated_at": datetime.now().isoformat(),
        "demo_mode": False,
        "source": "user_input"
    }


def save_product_profile(profile: Dict[str, Any], output_path: str = "data/product_profile.json"):
    """Save product profile to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print(f"✓ Product profile saved to {output_path}")
    return output_path


def validate_profile(profile: Dict[str, Any]) -> List[str]:
    """Validate profile has required fields."""
    errors = []
    required_fields = [
        "product_name", "one_liner", "category", "icp",
        "competitors", "positioning", "budget"
    ]

    for field in required_fields:
        if field not in profile:
            errors.append(f"Missing required field: {field}")

    if not profile.get("demo_mode") and not profile.get("url"):
        errors.append("Product URL missing. Include a URL/domain or add one to data/product_profile.json before running downstream scripts.")

    if "budget" in profile:
        budget = profile["budget"]
        if "weekly_usd" not in budget:
            errors.append("Budget missing weekly_usd")
        if "max_single_spend_usd" not in budget:
            errors.append("Budget missing max_single_spend_usd")

    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Flywheel product profile from real founder input.")
    parser.add_argument("product_context", nargs="*", help="Product context text. If omitted, stdin is used.")
    parser.add_argument("--demo", action="store_true", help="Use the explicit ExampleAI demo fixture.")
    parser.add_argument("--input-file", help="Read product context from a markdown/text file.")
    parser.add_argument("--output", default="data/product_profile.json", help="Output JSON path.")
    return parser


def main():
    """Main intake workflow."""
    parser = build_arg_parser()
    args = parser.parse_args()

    print("🚀 Flywheel Agent - Product Intake")
    print("Generating product profile for GTM operations...\n")

    try:
        if args.demo:
            profile = create_demo_profile()
        else:
            if args.input_file:
                with open(args.input_file, "r") as f:
                    raw_input = f.read()
            elif args.product_context:
                raw_input = " ".join(args.product_context)
            elif not sys.stdin.isatty():
                raw_input = sys.stdin.read()
            else:
                raw_input = ""
            profile = normalize_input(raw_input)
    except Exception as exc:
        print(f"❌ Intake error: {exc}")
        print("   Provide real product context, for example:")
        print("   python flywheel_intake.py 'Product: ExampleAI (https://example.ai) ICP: e-commerce founders Budget: $50 Focus: relaunch awareness'")
        print("   Or run an explicit fixture demo with: python flywheel_intake.py --demo")
        return 1

    errors = validate_profile(profile)
    if errors:
        print("❌ Profile validation errors:")
        for error in errors:
            print(f"   - {error}")
        return 1

    output_path = save_product_profile(profile, args.output)

    print("\n📊 Product Profile Summary:")
    print(f"   Product: {profile['product_name']}")
    print(f"   URL: {profile.get('url') or '[missing]'}")
    print(f"   Category: {profile['category']}")
    print(f"   Weekly Budget: ${profile['budget']['weekly_usd']}")
    print(f"   Max Single Spend: ${profile['budget']['max_single_spend_usd']}")
    print(f"   Competitors: {len(profile['competitors'])} found")

    if profile.get("demo_mode"):
        print("\n🎭 Running in EXPLICIT DEMO MODE - using ExampleAI fixture data")
    else:
        print("\n✅ Using founder-provided product context — no demo fixture data applied")

    print(f"\n✅ Intake complete! Profile ready for GTM operations: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
