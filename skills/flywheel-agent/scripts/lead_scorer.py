#!/usr/bin/env python3
"""
Lead Scorer Script
Scores leads and generates personalized outbound messages with approval gates.

Lead sources, in priority order:
1. --input <json>       agent research (key: "leads")
2. --leads-csv <csv>    founder-provided CSV (auto-detects data/leads.csv,
                        then data/prospects.csv)
3. bundled sample fixture, only when demo mode is explicit
Otherwise the script exits with EXIT_MISSING_INPUT and an actionable message.
"""

import copy
import csv
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from _common import (
    EXIT_ERROR,
    EXIT_MISSING_INPUT,
    EXIT_OK,
    anchor,
    artifact_demo_mode,
    build_parser,
    configure_stdout,
    exit_missing_input,
    fixture_allowed,
    get_pain_points,
    get_proof_points,
    load_profile,
    md_safe,
    out_path,
    resolve_research,
    write_json,
    write_text,
)

LEADS_SCHEMA_HINT = (
    "JSON with key 'leads': list of "
    "{name, title, company, bio, source, url, engagement_context}"
)

AUTO_CSV_CANDIDATES = ["data/leads.csv", "data/prospects.csv"]

# Sample leads for demo mode
SAMPLE_LEADS = [
    {
        "name": "Alex Rivera",
        "title": "Founder",
        "company": "CartPilot Labs",
        "bio": "Runs a fast-growing Shopify app team and is looking for better customer intelligence workflows.",
        "source": "LinkedIn engagement on e-commerce AI post",
        "url": "https://example.com/profiles/alex-rivera",
        "engagement_context": "Commented that early-stage e-commerce teams need clearer customer segment signals."
    },
    {
        "name": "Maya Chen",
        "title": "Head of Growth",
        "company": "ShopFlow Analytics",
        "bio": "Leads growth for an e-commerce analytics startup serving independent store operators.",
        "source": "Newsletter subscriber",
        "url": "https://example.com/profiles/maya-chen",
        "engagement_context": "Subscribed after reading about AI-assisted merchandising and retention workflows."
    },
    {
        "name": "Jordan Park",
        "title": "Founder",
        "company": "GrowthDock",
        "bio": "Builds tools for online merchants and frequently tests new customer acquisition channels.",
        "source": "Product Hunt engagement",
        "url": "https://example.com/profiles/jordan-park",
        "engagement_context": "Commented on a launch about replacing manual store analysis with better automation."
    },
    {
        "name": "Priya Shah",
        "title": "Product Lead",
        "company": "RetailOps Demo",
        "bio": "Owns product-led growth experiments for a small e-commerce operations platform.",
        "source": "Webinar attendee",
        "url": "https://example.com/profiles/priya-shah",
        "engagement_context": "Asked how AI can turn storefront data into weekly growth actions."
    },
    {
        "name": "Noah Kim",
        "title": "CEO",
        "company": "Catalog Labs",
        "bio": "Founder working on catalog enrichment and customer insight tooling for DTC brands.",
        "source": "Community discussion",
        "url": "https://example.com/profiles/noah-kim",
        "engagement_context": "Posted about needing simpler ways to prioritize campaigns from store data."
    },
    {
        "name": "Aisha Morgan",
        "title": "Founder",
        "company": "StackCart",
        "bio": "Runs a small e-commerce infrastructure startup focused on customer retention workflows.",
        "source": "X post engagement",
        "url": "https://example.com/profiles/aisha-morgan",
        "engagement_context": "Liked a thread about AI-native customer intelligence for online stores."
    },
    {
        "name": "Elena Brooks",
        "title": "Growth Engineer",
        "company": "Commerce Data Collective",
        "bio": "Builds internal dashboards and growth loops for e-commerce teams.",
        "source": "GitHub activity",
        "url": "https://example.com/profiles/elena-brooks",
        "engagement_context": "Starred several e-commerce intelligence repositories."
    },
    {
        "name": "Kenji Sato",
        "title": "Growth Operations Lead",
        "company": "Checkout Pathways",
        "bio": "Runs checkout optimization and lifecycle experiments for online stores.",
        "source": "Conference speaker list",
        "url": "https://example.com/profiles/kenji-sato",
        "engagement_context": "Talk title mentioned the limits of current growth planning tools."
    },
    {
        "name": "Sam Taylor",
        "title": "Founder",
        "company": "StoreWorks",
        "bio": "Building tooling for store operators who want lightweight customer intelligence.",
        "source": "Founder community",
        "url": "https://example.com/profiles/sam-taylor",
        "engagement_context": "Asked for recommendations on customer segment discovery tools."
    },
    {
        "name": "Riley Stone",
        "title": "Marketing Lead",
        "company": "LaunchOps Demo",
        "bio": "Runs launch and creator experiments for early-stage e-commerce products.",
        "source": "Launch community",
        "url": "https://example.com/profiles/riley-stone",
        "engagement_context": "Engaged with posts about weekly GTM sprint planning."
    }
]


def load_leads_from_csv(csv_path) -> List[Dict[str, Any]]:
    """Load leads from a CSV file (UTF-8)."""
    leads = []
    with anchor(csv_path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ragged rows produce None keys/values from DictReader; normalize
            # so downstream scoring and JSON serialization never crash.
            leads.append({(k or ""): ("" if v is None else v) for k, v in row.items()})
    return leads


def find_leads_csv(args) -> Optional[Path]:
    """Resolve a founder-provided leads CSV, if any."""
    if getattr(args, "leads_csv", None):
        csv_path = anchor(args.leads_csv)
        if not csv_path.exists():
            print(f"❌ Leads CSV not found: {csv_path}")
            print("   Check the --leads-csv path, or omit it to use --input research.")
            sys.exit(EXIT_MISSING_INPUT)
        return csv_path
    for candidate in AUTO_CSV_CANDIDATES:
        candidate_path = anchor(candidate)
        if candidate_path.exists():
            return candidate_path
    return None


def resolve_leads(args, profile):
    """Return (leads, data_source) following the documented priority order."""
    if getattr(args, "input_path", None):
        return resolve_research(args, profile, "leads", LEADS_SCHEMA_HINT)

    csv_path = find_leads_csv(args)
    if csv_path is not None:
        leads = load_leads_from_csv(csv_path)
        if leads:
            print(f"✓ Found leads CSV at {csv_path}")
            return leads, "founder_csv"
        print(f"⚠️  Leads CSV at {csv_path} has no rows; looking for other sources.")

    if fixture_allowed(args, profile):
        print("ℹ️  Demo mode - using bundled sample leads")
        return copy.deepcopy(SAMPLE_LEADS), "sample_fixture"

    extra_lines = []
    if anchor("data/leads.example.csv").exists():
        extra_lines.append("Or copy data/leads.example.csv to data/leads.csv or pass --leads-csv <path>.")
    exit_missing_input("leads", LEADS_SCHEMA_HINT, extra_lines)


def calculate_icp_fit_score(lead: Dict[str, Any], profile: Dict[str, Any]) -> int:
    """Calculate how well a lead fits the ICP (0-100)."""

    score = 0
    icp = profile.get("icp", {})

    # Get lead data (research values may be non-strings; degrade, don't crash)
    title = str(lead.get("title") or "").lower()
    company = str(lead.get("company") or "").lower()
    bio = str(lead.get("bio") or "").lower()

    # ICP buyer match
    icp_buyer = icp.get("buyer", "").lower()
    if icp_buyer and (icp_buyer in title or icp_buyer in bio):
        score += 25

    # Pain point keyword matching
    pain_points = icp.get("pain_points", []) or []
    keywords = icp.get("keywords", []) or []

    all_keywords = list(pain_points) + list(keywords)
    text_to_check = f"{title} {bio} {str(lead.get('engagement_context') or '')}".lower()

    keyword_matches = 0
    for keyword in all_keywords:
        if str(keyword).lower() in text_to_check:
            keyword_matches += 1

    # Score based on keyword matches (up to 40 points)
    score += min(40, keyword_matches * 8)

    # Company stage/size indicators
    stage_indicators = ["startup", "founder", "cto", "early", "series", "seed"]
    size_indicators = ["small", "team", "lead", "principal", "senior"]

    for indicator in stage_indicators:
        if indicator in title or indicator in company:
            score += 10
            break

    for indicator in size_indicators:
        if indicator in title:
            score += 5
            break

    # Engagement quality bonus
    engagement = str(lead.get("engagement_context") or "").lower()
    positive_signals = ["exactly", "need", "interested", "looking", "building", "better"]

    for signal in positive_signals:
        if signal in engagement:
            score += 5

    return min(100, score)


def build_proof_sentence(profile: Dict[str, Any]) -> str:
    """One natural sentence of social proof for outbound copy.

    Uses the first positioning proof point (quoted so it reads naturally).
    Returns an empty string when no proof points exist - callers decide
    whether to fall back to the one-liner or drop the paragraph. Never
    pulls from positioning.review_notes (internal disclaimers).
    """
    proof_points = get_proof_points(profile)
    if proof_points:
        proof = proof_points[0].rstrip(".")
        return f'Early feedback has been encouraging, with users telling us: "{proof}."'
    return ""


def generate_personalized_message(lead: Dict[str, Any], profile: Dict[str, Any], score: int) -> str:
    """Generate personalized outbound message for lead."""

    name = str(lead.get("name") or "there")
    company = str(lead.get("company") or "your company")
    title = str(lead.get("title") or "")
    engagement = str(lead.get("engagement_context") or "")
    source = str(lead.get("source") or "")

    product_name = profile.get("product_name", "our product")
    one_liner = str(profile.get("one_liner", "") or "").strip().rstrip(".")
    url = profile.get("url", "")

    # Get main pain point
    icp = profile.get("icp", {})
    pain_points = get_pain_points(profile)
    main_pain = pain_points[0] if pain_points else "workflow challenges"
    buyer = icp.get("buyer") or "professionals"
    buyer_plural = buyer if buyer.endswith("s") else f"{buyer}s"
    category = profile.get("category", "industry")

    # Social proof paragraph (quoted proof point, or one-liner fallback)
    proof_sentence = build_proof_sentence(profile)
    one_liner_sentence = f"In one line: {one_liner}." if one_liner else ""

    # What the lead did that put them on our radar. URLs contain ":" too,
    # and "I noticed your https..." reads broken - fall back for those.
    engagement_ref = "recent activity"
    if ":" in engagement:
        prefix = engagement.split(":")[0].strip()
        if prefix and "http" not in prefix.lower():
            engagement_ref = prefix

    # Generate message based on engagement context and score
    if score >= 80:
        # High-fit personalized message
        proof_para = proof_sentence or one_liner_sentence
        if proof_para:
            proof_para += f" That could be a game changer for {company}'s {category} work."
        paragraphs = [
            f"Hi {name},",
            f"I noticed your {engagement_ref} about {main_pain} - it really resonated with what we're seeing across the {category}.",
            f"As a {title} at {company}, you might be interested in {product_name} ({url}). We built it specifically for professionals dealing with {main_pain}.",
            proof_para,
            "Would love to get your thoughts if you have 5 minutes to check it out. Happy to answer any questions!",
            "Best,\n[Your name]",
        ]

    elif score >= 60:
        # Medium-fit targeted message
        proof_para = proof_sentence
        if proof_para:
            proof_para += " It could help with the challenges you mentioned."
        paragraphs = [
            f"Hi {name},",
            f"Saw your activity around {source.split()[0] if source else 'the space'} and thought {product_name} might be relevant for your work at {company}.",
            f"{one_liner or product_name} - specifically designed for {buyer_plural} who need better solutions for {main_pain}.",
            proof_para,
            f"Worth a quick look: {url}",
            "Best,\n[Your name]",
        ]

    else:
        # Lower-fit generic message
        paragraphs = [
            f"Hi {name},",
            f"I came across your work at {company} and thought you might be interested in {product_name}.",
            f"{one_liner or product_name} - we built it to help {buyer_plural} overcome {main_pain}.",
            proof_sentence,
            f"Check it out if it seems relevant: {url}",
            "Best,\n[Your name]",
        ]

    return "\n\n".join(p for p in paragraphs if p).strip()


def score_and_personalize_leads(leads: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Score all leads and generate personalized messages."""

    scored_leads = []

    for lead in leads:
        # Calculate ICP fit score
        score = calculate_icp_fit_score(lead, profile)

        # Generate personalized message
        message = generate_personalized_message(lead, profile, score)

        # Add scoring and message data
        enhanced_lead = lead.copy()
        enhanced_lead.update({
            "icp_fit_score": score,
            "personalized_message": message,
            "message_drafts": {
                "dm": message,
                "email": message,
                "reply": message
            },
            "approval_required": True,
            "requires_human_approval": True,
            "status": "draft",
            "priority": "high" if score >= 80 else "medium" if score >= 60 else "low"
        })

        scored_leads.append(enhanced_lead)

    # Sort by score descending
    scored_leads.sort(key=lambda x: x["icp_fit_score"], reverse=True)

    return scored_leads


def save_lead_queue(args, scored_leads: List[Dict[str, Any]], profile: Dict[str, Any], data_source: str):
    """Save scored leads and outbound queue to JSON + markdown."""

    json_path = out_path(args, "outbound_queue.json")

    data = {
        "generated_at": datetime.now().isoformat(),
        "total_leads": len(scored_leads),
        "high_priority": len([l for l in scored_leads if l["priority"] == "high"]),
        "medium_priority": len([l for l in scored_leads if l["priority"] == "medium"]),
        "low_priority": len([l for l in scored_leads if l["priority"] == "low"]),
        "avg_score": sum(l["icp_fit_score"] for l in scored_leads) / len(scored_leads) if scored_leads else 0,
        "leads": scored_leads,
        "demo_mode": artifact_demo_mode(profile, data_source),
        "data_source": data_source,
    }

    write_json(json_path, data)
    print(f"✓ Outbound queue saved to {json_path}")

    # Also save markdown summary
    md_path = out_path(args, "outbound_queue.md")
    save_queue_markdown(data, md_path)

    return json_path


def save_queue_markdown(data: Dict[str, Any], output_path):
    """Save human-readable outbound queue markdown."""

    leads = data["leads"]

    md_content = f"""# Warm Outbound Queue

Generated: {data['generated_at']}
**Total Leads:** {data['total_leads']}
**Average ICP Fit:** {data['avg_score']:.1f}/100
**Demo Mode:** {data.get('demo_mode', False)}
**Data Source:** {data.get('data_source', 'unknown')}

## Priority Breakdown
- 🔥 High Priority (80+ score): {data['high_priority']} leads
- 🟡 Medium Priority (60-79): {data['medium_priority']} leads
- 🔵 Low Priority (<60): {data['low_priority']} leads

## Outbound Queue (Priority Order)

"""

    for i, lead in enumerate(leads, 1):
        priority_emoji = "🔥" if lead["priority"] == "high" else "🟡" if lead["priority"] == "medium" else "🔵"

        md_content += f"""### {i}. {md_safe(lead.get('name', 'Unknown'))} - {md_safe(lead.get('title', 'N/A'))} {priority_emoji}

**Company:** {md_safe(lead.get('company', 'N/A'))} | **ICP Fit Score:** {lead['icp_fit_score']}/100 | **Priority:** {lead['priority'].title()}
**Source:** {md_safe(lead.get('source', 'N/A'))}
**Profile:** {md_safe(lead.get('url', 'N/A'))}

**Engagement Context:** {md_safe(lead.get('engagement_context', 'N/A'))}

**Personalized Message:**
```
{md_safe(lead['personalized_message'])}
```

**Approval Required:** ✅ YES
**Status:** {lead['status']}

---

"""

    md_content += """## Outreach Guidelines

### Message Timing
- **High Priority:** Reach out within 1-2 days
- **Medium Priority:** Reach out within 1 week
- **Low Priority:** Reach out within 2 weeks

### Personalization Tips
1. Reference specific engagement context
2. Connect to their company's likely challenges
3. Keep initial message under 100 words
4. Include clear call-to-action
5. Follow up once after 1 week if no response

## Next Steps

1. ✅ Review lead scores and prioritization
2. ⚠️  **Get approval before sending ANY outbound messages**
3. 📝 Customize messages with specific details about their company/role
4. 📅 Schedule outreach over several days to avoid spam appearance
5. 📊 Track response rates by priority level and engagement source

**SAFETY REMINDER:** All outbound requires explicit human approval before sending.
"""

    write_text(output_path, md_content)

    print(f"✓ Queue markdown saved to {output_path}")


def main():
    """Main lead scoring workflow."""
    configure_stdout()
    print("🎯 Flywheel Agent - Lead Scorer")
    print("Scoring leads and generating warm outbound queue...\n")

    parser = build_parser("Score leads and draft approval-gated outbound messages.")
    parser.add_argument(
        "--leads-csv",
        dest="leads_csv",
        help=(
            "Path to a founder-provided leads CSV "
            "(auto-detects data/leads.csv, then data/prospects.csv)."
        ),
    )
    args = parser.parse_args()

    try:
        # Load product profile
        profile = load_profile(args)
        print(f"✓ Loaded profile for {profile.get('product_name', 'unknown product')}")

        # Get leads data (--input research > founder CSV > demo fixture > exit 2)
        leads, data_source = resolve_leads(args, profile)
        print(f"✓ Loaded {len(leads)} leads ({data_source})")

        if not leads:
            print("⚠️  No leads found. Add data/leads.csv or pass --input research to score leads.")
            return EXIT_ERROR

        # Score and personalize leads
        scored_leads = score_and_personalize_leads(leads, profile)

        # Save outbound queue
        save_lead_queue(args, scored_leads, profile, data_source)

        # Print summary
        print(f"\n📊 Lead Scoring Summary:")
        print(f"   Total Leads: {len(scored_leads)}")
        print(f"   High Priority: {len([l for l in scored_leads if l['priority'] == 'high'])}")
        print(f"   Average Score: {sum(l['icp_fit_score'] for l in scored_leads) / len(scored_leads):.1f}/100")
        print(f"   Top Lead: {scored_leads[0].get('name', 'Unknown')} ({scored_leads[0]['icp_fit_score']}/100)")

        if data_source == "sample_fixture":
            print("\n🎭 Running in DEMO MODE - using sample lead data")

        print(f"\n✅ Lead scoring complete! Review and approve messages before sending.")
        return EXIT_OK

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Unexpected error: {e}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
