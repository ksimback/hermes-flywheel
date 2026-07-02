#!/usr/bin/env python3
"""
Creator Campaign Script
Plans influencer partnerships with performance incentives and approval-gated spend.

Creator sources: agent research via --input (key: "creators"), or the bundled
sample fixture when demo mode is explicit. Otherwise exits with
EXIT_MISSING_INPUT and an actionable message.
"""

import copy
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List

from _common import (
    EXIT_ERROR,
    EXIT_OK,
    artifact_demo_mode,
    build_parser,
    configure_stdout,
    get_pain_points,
    get_proof_points,
    load_profile,
    md_cell,
    md_safe,
    out_path,
    resolve_research,
    safe_number,
    write_json,
    write_text,
)

CREATORS_SCHEMA_HINT = (
    "JSON with key 'creators': list of "
    "{name, platform, followers, niche, engagement_rate, content_type, "
    "avg_views, profile_url, recent_content, audience_match, estimated_rate}"
)

# Spend guardrails asserted by the test suite
MIN_SPEND_USD = 15
MAX_SPEND_USD = 300

# Sample creators for demo mode
SAMPLE_CREATORS = [
    {
        "name": "StoreGrowthDemo",
        "platform": "YouTube",
        "followers": 45000,
        "niche": "e-commerce intelligence",
        "engagement_rate": 4.2,
        "content_type": ["tutorials", "tool reviews", "industry insights"],
        "avg_views": 8500,
        "profile_url": "https://example.com/creators/store-growth-demo",
        "recent_content": "Recent videos about storefront builders for e-commerce, growth planning software reviews",
        "audience_match": "e-commerce founders, e-commerce industry professionals",
        "estimated_rate": 250
    },
    {
        "name": "CommerceToolbox",
        "platform": "Twitter",
        "followers": 28000,
        "niche": "e-commerce technology",
        "engagement_rate": 6.8,
        "content_type": ["thread tutorials", "tool spotlights", "startup features"],
        "avg_views": 15000,
        "profile_url": "https://example.com/creators/commerce-toolbox",
        "recent_content": "Threads about e-commerce software, startup tooling, engineering productivity",
        "audience_match": "e-commerce startup founders, e-commerce founders",
        "estimated_rate": 150
    },
    {
        "name": "CommerceAdvocateDemo",
        "platform": "LinkedIn",
        "followers": 12000,
        "niche": "e-commerce careers & tools",
        "engagement_rate": 8.1,
        "content_type": ["industry posts", "career advice", "tool recommendations"],
        "avg_views": 3500,
        "profile_url": "https://example.com/creators/commerce-advocate-demo",
        "recent_content": "Posts about e-commerce intelligence careers, software recommendations, industry trends",
        "audience_match": "e-commerce professionals, engineering students",
        "estimated_rate": 100
    },
    {
        "name": "StoreGrowthDaily",
        "platform": "TikTok",
        "followers": 18500,
        "niche": "engineering software demos",
        "engagement_rate": 12.4,
        "content_type": ["software demos", "quick tutorials", "before/after comparisons"],
        "avg_views": 25000,
        "profile_url": "https://example.com/creators/store-growth-daily",
        "recent_content": "Short demos of engineering tools, software comparisons, productivity tips",
        "audience_match": "young engineers, e-commerce students, early-career professionals",
        "estimated_rate": 200
    }
]

CAMPAIGN_TEMPLATES = {
    "tool_review": {
        "name": "Software Tool Review Campaign",
        "description": "Detailed review of the product with demo and commentary",
        "deliverables": ["5-10 minute video review", "written post/thread", "demo walkthrough"],
        "timeline": "2 weeks",
        "performance_metrics": ["views", "clicks", "signups"]
    },
    "tutorial_series": {
        "name": "Tutorial Integration Campaign",
        "description": "Multi-part tutorial series featuring the product",
        "deliverables": ["3-part tutorial series", "code/examples", "follow-up posts"],
        "timeline": "1 month",
        "performance_metrics": ["series completion", "engagement", "conversions"]
    },
    "launch_spotlight": {
        "name": "Launch Week Spotlight",
        "description": "Featured coverage during product launch week",
        "deliverables": ["launch announcement post", "demo video", "audience Q&A"],
        "timeline": "1 week",
        "performance_metrics": ["launch week traffic", "social shares", "mentions"]
    },
    "case_study": {
        "name": "Real-World Case Study",
        "description": "Creator uses product for actual project and documents results",
        "deliverables": ["project documentation", "results video", "before/after comparison"],
        "timeline": "3 weeks",
        "performance_metrics": ["project completion", "results demonstration", "audience engagement"]
    }
}


def find_relevant_creators(creators: List[Dict[str, Any]], profile: Dict[str, Any],
                           data_source: str) -> List[Dict[str, Any]]:
    """Score creators for relevance to the product category and ICP."""

    # Agent-researched creators were already vetted upstream; only the broad
    # sample fixture gets filtered by the relevance threshold.
    min_score = 60 if data_source == "sample_fixture" else 0

    relevant_creators = []
    for creator in creators:
        creator = copy.deepcopy(creator)
        score = calculate_creator_relevance(creator, profile)
        if score >= min_score:
            creator["relevance_score"] = score
            relevant_creators.append(creator)

    # Sort by relevance score
    relevant_creators.sort(key=lambda x: x["relevance_score"], reverse=True)

    return relevant_creators


def calculate_creator_relevance(creator: Dict[str, Any], profile: Dict[str, Any]) -> int:
    """Calculate how relevant a creator is to the product (0-100)."""

    score = 0

    # Niche match (research values may be non-strings; degrade, don't crash)
    creator_niche = str(creator.get("niche") or "").lower()
    category = profile.get("category", "").lower()

    if category and creator_niche and (category in creator_niche or creator_niche in category):
        score += 30
    elif "engineering" in creator_niche and "software" in category:
        score += 20
    elif "tech" in creator_niche:
        score += 10

    # Audience match
    audience = str(creator.get("audience_match") or "").lower()
    icp_buyer = profile.get("icp", {}).get("buyer", "").lower()

    if icp_buyer and icp_buyer in audience:
        score += 25
    elif "engineer" in audience and "engineer" in icp_buyer:
        score += 20
    elif "professional" in audience:
        score += 10

    # Content type relevance
    content_types = creator.get("content_type", []) or []
    if "tool reviews" in content_types or "software demos" in content_types:
        score += 20
    elif "tutorials" in content_types:
        score += 15
    elif any("tool" in str(ct) or "software" in str(ct) for ct in content_types):
        score += 10

    # Engagement quality bonus
    engagement_rate = safe_number(creator.get("engagement_rate", 0), 0)
    if engagement_rate > 8:
        score += 10
    elif engagement_rate > 5:
        score += 5

    # Platform bonus for certain categories
    platform = str(creator.get("platform") or "").lower()
    if platform == "youtube" and "software" in category:
        score += 5
    elif platform == "linkedin" and "b2b" in category:
        score += 5

    return min(100, score)


def generate_campaign_proposals(creators: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate campaign proposals for each relevant creator."""

    proposals = []

    for creator in creators:
        # Select best campaign type for this creator
        campaign_type = select_campaign_type(creator, profile)
        campaign_template = CAMPAIGN_TEMPLATES[campaign_type]

        # Calculate pricing (research values may be strings; degrade safely)
        base_rate = int(safe_number(creator.get("estimated_rate", 100), 100))
        performance_bonus = int(base_rate * 0.5)  # 50% performance bonus
        total_budget = base_rate + performance_bonus

        # Generate campaign proposal
        proposal = {
            "creator": creator.get("name", "Unknown creator"),
            "platform": creator.get("platform", "Unknown"),
            "followers": int(safe_number(creator.get("followers", 0), 0)),
            "relevance_score": creator["relevance_score"],
            "campaign_type": campaign_type,
            "campaign_name": campaign_template["name"],
            "description": campaign_template["description"],
            "deliverables": campaign_template["deliverables"],
            "timeline": campaign_template["timeline"],
            "pricing": {
                "base_fee": base_rate,
                "performance_bonus": performance_bonus,
                "total_budget": total_budget,
                "payment_terms": "50% upfront, 50% on delivery + bonus on performance"
            },
            "performance_metrics": campaign_template["performance_metrics"],
            "campaign_brief": generate_campaign_brief(creator, profile, campaign_template),
            "approval_required": True,
            "status": "proposal"
        }

        proposals.append(proposal)

    return proposals


def select_campaign_type(creator: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """Select best campaign type for creator and product."""

    platform = str(creator.get("platform") or "").lower()
    content_types = creator.get("content_type", []) or []

    # Platform-based selection
    if platform == "youtube":
        if "tool reviews" in content_types:
            return "tool_review"
        elif "tutorials" in content_types:
            return "tutorial_series"
        else:
            return "case_study"
    elif platform == "tiktok":
        return "tool_review"  # Short demo format works best
    elif platform == "twitter":
        return "launch_spotlight"  # Good for launch buzz
    elif platform == "linkedin":
        return "case_study"  # Professional case studies work well

    # Default fallback
    return "tool_review"


def generate_campaign_brief(creator: Dict[str, Any], profile: Dict[str, Any], campaign_template: Dict[str, Any]) -> str:
    """Generate campaign brief for creator."""

    product_name = profile.get("product_name", "Product")
    one_liner = profile.get("one_liner", "Revolutionary solution")
    url = profile.get("url", "")

    # Key messaging. proof_points may be empty for real founder profiles -
    # fall back to the one-liner and never pull from positioning.review_notes.
    proof_points = get_proof_points(profile)
    main_proof = proof_points[0] if proof_points else one_liner

    # Target audience
    icp = profile.get("icp", {})
    buyer = icp.get('buyer') or 'professionals'
    buyer_plural = buyer if buyer.endswith('s') else f"{buyer}s"
    target_audience = f"{buyer_plural} in {profile.get('category', 'the industry')}"

    pain_points = get_pain_points(profile)
    main_pain = pain_points[0] if pain_points else "workflow challenges"

    brief = f"""# Campaign Brief: {campaign_template['name']}

## Product Overview
**Product:** {product_name} ({url})
**Description:** {one_liner}
**Key Benefit:** {main_proof}
**Target Audience:** {target_audience}

## Campaign Concept
{campaign_template['description']}

## Deliverables
{chr(10).join(f"- {deliverable}" for deliverable in campaign_template['deliverables'])}

## Key Messages
- {product_name} solves {main_pain}
- {main_proof}
- Built specifically for {target_audience}
- Modern alternative to legacy solutions

## Content Guidelines
- Keep focus on practical value and real-world use cases
- Show actual product interface and workflows
- Include your honest opinion and any limitations you notice
- Encourage audience questions and engagement
- Use provided discount code: CREATOR20 (20% off)

## Timeline
{campaign_template['timeline']} from agreement to delivery

## Success Metrics
{chr(10).join(f"- {metric}" for metric in campaign_template['performance_metrics'])}

## Assets Provided
- Product demo account/access
- High-res screenshots and logos
- Key messaging document
- Technical documentation as needed

## Creative Freedom
You have full creative control over content style and format. This brief provides direction, but we trust your expertise on what resonates with your audience.
"""

    return brief


def generate_spend_requests(proposals: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate Stripe spend requests for creator campaigns."""

    spend_requests = []

    budget = profile.get("budget", {}) or {}
    weekly_usd = int(safe_number(budget.get("weekly_usd", 100), 100))
    max_single_spend = int(safe_number(budget.get("max_single_spend_usd", 0), 0))

    for proposal in proposals:
        pricing = proposal["pricing"]

        # Initial payment request (50% upfront), clamped DOWN to the tightest
        # guardrail: never above half the base fee, the global MAX_SPEND_USD,
        # or the founder's max_single_spend_usd. There is no floor - a request
        # must never be raised above what the creator actually charges. Skip
        # creators whose clamped amount falls below the minimum viable spend.
        upfront_amount = pricing["base_fee"] // 2
        upfront_amount = min(upfront_amount, MAX_SPEND_USD)
        if max_single_spend > 0:
            upfront_amount = min(upfront_amount, max_single_spend)
        if upfront_amount < MIN_SPEND_USD:
            print(f"⚠️  Skipping spend request for {proposal.get('creator', 'creator')}: "
                  f"clamped amount ${upfront_amount} is below the ${MIN_SPEND_USD} minimum.")
            continue

        i = len(spend_requests)
        spend_request = {
            "id": f"spend_{i+1:03d}",
            "campaign_id": f"creator_campaign_{i+1:03d}",
            "creator": proposal["creator"],
            "amount_usd": upfront_amount,
            "purpose": f"Creator campaign upfront payment - {proposal['campaign_name']}",
            "description": f"50% upfront payment for {proposal['creator']} {proposal['campaign_type']} campaign",
            "expected_outcome": f"{', '.join(proposal['deliverables'])}",
            "performance_bonus_potential": pricing["performance_bonus"],
            "total_campaign_budget": pricing["total_budget"],
            "approval_status": "pending",
            "requires_approval": True,
            "stripe_mode": "test",
            "payment_terms": pricing["payment_terms"],
            "created_at": datetime.now().isoformat(),
            "budget_impact": {
                "weekly_budget": weekly_usd,
                "max_single_spend": max_single_spend if max_single_spend > 0 else 25,
                "exceeds_single_limit": upfront_amount > (max_single_spend if max_single_spend > 0 else 25),
                "percentage_of_weekly": round((upfront_amount / max(1, weekly_usd)) * 100, 1)
            }
        }

        spend_requests.append(spend_request)

    return spend_requests


def save_creator_campaign(args, proposals: List[Dict[str, Any]], spend_requests: List[Dict[str, Any]],
                          profile: Dict[str, Any], data_source: str):
    """Save creator campaign and spend requests to JSON + markdown."""

    json_path = out_path(args, "creator_campaign.json")

    data = {
        "generated_at": datetime.now().isoformat(),
        "total_proposals": len(proposals),
        "total_budget": sum(p["pricing"]["total_budget"] for p in proposals),
        "avg_relevance_score": sum(p["relevance_score"] for p in proposals) / len(proposals) if proposals else 0,
        "campaign_proposals": proposals,
        "spend_requests": spend_requests,
        "demo_mode": artifact_demo_mode(profile, data_source),
        "data_source": data_source,
    }

    write_json(json_path, data)
    print(f"✓ Creator campaign saved to {json_path}")

    # Also save markdown summary
    md_path = out_path(args, "creator_campaign.md")
    save_campaign_markdown(data, md_path)

    return json_path


def save_campaign_markdown(data: Dict[str, Any], output_path):
    """Save human-readable creator campaign markdown."""

    proposals = data["campaign_proposals"]
    spend_requests = data["spend_requests"]

    md_content = f"""# Creator Campaign Strategy

Generated: {data['generated_at']}
**Total Proposals:** {data['total_proposals']}
**Total Budget:** ${data['total_budget']:,}
**Average Relevance:** {data['avg_relevance_score']:.1f}/100
**Demo Mode:** {data.get('demo_mode', False)}
**Data Source:** {data.get('data_source', 'unknown')}

## Campaign Proposals (Relevance Order)

"""

    for i, proposal in enumerate(proposals, 1):
        pricing = proposal["pricing"]

        md_content += f"""### {i}. {md_safe(proposal['creator'])} - {proposal['campaign_name']}

**Platform:** {md_safe(proposal['platform'])} | **Followers:** {proposal['followers']:,} | **Relevance:** {proposal['relevance_score']}/100

**Campaign Type:** {proposal['campaign_type']}
**Timeline:** {proposal['timeline']}

**Pricing:**
- Base Fee: ${pricing['base_fee']}
- Performance Bonus: ${pricing['performance_bonus']}
- Total Budget: ${pricing['total_budget']}
- Terms: {pricing['payment_terms']}

**Deliverables:**
{chr(10).join(f"- {deliverable}" for deliverable in proposal['deliverables'])}

**Performance Metrics:** {', '.join(proposal['performance_metrics'])}

**Campaign Brief:**
```
{md_safe(proposal['campaign_brief'])}
```

**Approval Required:** ✅ YES
**Status:** {proposal['status']}

---

"""

    md_content += """## Spend Requests Summary

| Creator | Upfront Payment | Performance Bonus | Total Budget | Exceeds Limit? |
|---------|----------------|------------------|-------------|----------------|
"""

    for req in spend_requests:
        exceeds = "⚠️ YES" if req["budget_impact"]["exceeds_single_limit"] else "✅ NO"
        md_content += f"| {md_cell(req['creator'])} | ${req['amount_usd']} | ${req['performance_bonus_potential']} | ${req['total_campaign_budget']} | {exceeds} |\n"

    total_upfront = sum(req["amount_usd"] for req in spend_requests)

    md_content += f"""
**Total Upfront Spend:** ${total_upfront}
**Total Campaign Budget:** ${sum(req['total_campaign_budget'] for req in spend_requests)}

## Budget Impact Analysis

"""

    for req in spend_requests:
        impact = req["budget_impact"]
        status = "⚠️ EXCEEDS LIMIT" if impact["exceeds_single_limit"] else "✅ Within Limits"

        md_content += f"""### {md_safe(req['creator'])} Payment - {status}
- **Amount:** ${req['amount_usd']} ({impact['percentage_of_weekly']}% of weekly budget)
- **Single Spend Limit:** ${impact['max_single_spend']}
- **Weekly Budget:** ${impact['weekly_budget']}

"""

    md_content += """## Campaign Execution Plan

### Phase 1: Approval & Contracts (Week 1)
1. ✅ Review campaign proposals and select top 2-3 creators
2. ⚠️  **Get approval for spend requests before proceeding**
3. 📝 Send campaign briefs to approved creators
4. 📋 Execute contracts and initial payments

### Phase 2: Content Creation (Weeks 2-4)
1. 🎬 Creators develop content per campaign briefs
2. 📱 Provide product access and assets as needed
3. 📊 Track progress and provide feedback
4. 🔄 Review content before publication

### Phase 3: Launch & Performance (Weeks 4-6)
1. 🚀 Coordinate content publication timing
2. 📈 Track performance metrics
3. 💰 Execute performance bonuses based on results
4. 📋 Gather learnings for future campaigns

## Next Steps

1. ✅ Review creator relevance scores and campaign fit
2. ⚠️  **Get approval for ALL spend before executing payments**
3. 📝 Customize campaign briefs with specific product details
4. 💳 Set up Stripe payment infrastructure for creator payments
5. 📊 Define tracking systems for performance bonuses

**SAFETY REMINDER:** All creator payments require explicit approval before execution.
"""

    write_text(output_path, md_content)

    print(f"✓ Campaign markdown saved to {output_path}")


def main():
    """Main creator campaign workflow."""
    configure_stdout()
    print("🎬 Flywheel Agent - Creator Campaign Planner")
    print("Planning influencer partnerships with performance incentives...\n")

    parser = build_parser("Plan approval-gated creator campaigns with performance incentives.")
    args = parser.parse_args()

    try:
        # Load product profile
        profile = load_profile(args)
        print(f"✓ Loaded profile for {profile.get('product_name', 'unknown product')}")

        # Resolve creator research (--input research > demo fixture > exit 2)
        candidate_creators, data_source = resolve_research(
            args, profile, "creators", CREATORS_SCHEMA_HINT, fixture=SAMPLE_CREATORS
        )

        # Find relevant creators
        creators = find_relevant_creators(candidate_creators, profile, data_source)
        print(f"✓ Found {len(creators)} relevant creators ({data_source})")

        if not creators:
            print("⚠️  No relevant creators found for this product category.")
            return EXIT_ERROR

        # Generate campaign proposals
        proposals = generate_campaign_proposals(creators, profile)
        print(f"✓ Generated {len(proposals)} campaign proposals")

        # Generate spend requests
        spend_requests = generate_spend_requests(proposals, profile)
        print(f"✓ Generated {len(spend_requests)} spend requests")

        # Save campaign plan
        save_creator_campaign(args, proposals, spend_requests, profile, data_source)

        # Print summary
        total_budget = sum(p["pricing"]["total_budget"] for p in proposals)
        total_upfront = sum(req["amount_usd"] for req in spend_requests)

        print(f"\n📊 Creator Campaign Summary:")
        print(f"   Campaign Proposals: {len(proposals)}")
        print(f"   Total Budget: ${total_budget}")
        print(f"   Upfront Spend: ${total_upfront}")
        print(f"   Top Creator: {proposals[0]['creator']} ({proposals[0]['relevance_score']}/100)")

        # Budget warnings
        weekly_budget = profile.get("budget", {}).get("weekly_usd", 100)
        if total_upfront > weekly_budget:
            print(f"   ⚠️  Upfront spend (${total_upfront}) exceeds weekly budget (${weekly_budget})")

        if data_source == "sample_fixture":
            print("\n🎭 Running in DEMO MODE - using sample creator data")

        print(f"\n✅ Creator campaign complete! Review and approve spend before execution.")
        return EXIT_OK

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Unexpected error: {e}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
