#!/usr/bin/env python3
"""
Lead Scorer Script
Scores leads and generates personalized outbound messages with approval gates.
"""

import json
import os
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional

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


def load_product_profile(path: str = "data/product_profile.json") -> Dict[str, Any]:
    """Load product profile from JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Product profile not found at {path}. Run flywheel_intake.py first.")

    with open(path, 'r') as f:
        return json.load(f)

def load_leads_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Load leads from CSV file if provided."""
    if not os.path.exists(csv_path):
        return []

    leads = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(dict(row))

    return leads

def get_leads_data(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get leads data from CSV or use sample data."""

    # Check for CSV files in common locations
    csv_paths = [
        "data/leads.csv",
        "data/prospects.csv",
        "leads.csv",
        "prospects.csv"
    ]

    for csv_path in csv_paths:
        if os.path.exists(csv_path):
            print(f"✓ Found leads CSV at {csv_path}")
            return load_leads_from_csv(csv_path)

    # Use sample data for demo
    print("ℹ️  No leads CSV found, using sample data")
    return SAMPLE_LEADS

def calculate_icp_fit_score(lead: Dict[str, Any], profile: Dict[str, Any]) -> int:
    """Calculate how well a lead fits the ICP (0-100)."""

    score = 0
    icp = profile.get("icp", {})

    # Get lead data
    title = lead.get("title", "").lower()
    company = lead.get("company", "").lower()
    bio = lead.get("bio", "").lower()

    # ICP buyer match
    icp_buyer = icp.get("buyer", "").lower()
    if icp_buyer in title or icp_buyer in bio:
        score += 25

    # Pain point keyword matching
    pain_points = icp.get("pain_points", [])
    keywords = icp.get("keywords", [])

    all_keywords = pain_points + keywords
    text_to_check = f"{title} {bio} {lead.get('engagement_context', '')}".lower()

    keyword_matches = 0
    for keyword in all_keywords:
        if keyword.lower() in text_to_check:
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
    engagement = lead.get("engagement_context", "").lower()
    positive_signals = ["exactly", "need", "interested", "looking", "building", "better"]

    for signal in positive_signals:
        if signal in engagement:
            score += 5

    return min(100, score)

def generate_personalized_message(lead: Dict[str, Any], profile: Dict[str, Any], score: int) -> str:
    """Generate personalized outbound message for lead."""

    name = lead.get("name", "there")
    company = lead.get("company", "your company")
    title = lead.get("title", "")
    engagement = lead.get("engagement_context", "")
    source = lead.get("source", "")

    product_name = profile.get("product_name", "our product")
    one_liner = profile.get("one_liner", "innovative solution")
    url = profile.get("url", "")

    # Get main pain point and proof point
    icp = profile.get("icp", {})
    pain_points = icp.get("pain_points", ["workflow inefficiencies"])
    main_pain = pain_points[0] if pain_points else "workflow challenges"
    buyer = icp.get('buyer', 'professionals')
    buyer_plural = buyer if buyer.endswith('s') else f"{buyer}s"

    positioning = profile.get("positioning", {})
    proof_points = positioning.get("proof_points", ["significant improvements"])
    main_proof = proof_points[0] if proof_points else "better performance"

    # Generate message based on engagement context and score
    if score >= 80:
        # High-fit personalized message
        message = f"""Hi {name},

I noticed your {engagement.split(':')[0] if ':' in engagement else 'engagement'} about {main_pain} - it really resonated with what we're seeing across the {profile.get('category', 'industry')}.

As a {title} at {company}, you might be interested in {product_name} ({url}). We built it specifically for professionals dealing with {main_pain}.

{main_proof} - which could be a game changer for {company}'s {profile.get('category', 'operations')}.

Would love to get your thoughts if you have 5 minutes to check it out. Happy to answer any questions!

Best,
[Your name]"""

    elif score >= 60:
        # Medium-fit targeted message
        message = f"""Hi {name},

Saw your activity around {source.split()[0] if source else 'e-commerce tools'} and thought {product_name} might be relevant for your work at {company}.

{one_liner} - specifically designed for {buyer_plural} who need better solutions for {main_pain}.

{main_proof}, which could help with the challenges you mentioned.

Worth a quick look: {url}

Best,
[Your name]"""

    else:
        # Lower-fit generic message
        message = f"""Hi {name},

I came across your work at {company} and thought you might be interested in {product_name}.

{one_liner} - we built it to help {buyer_plural} overcome {main_pain}.

Early feedback has been positive, with users reporting {main_proof}.

Check it out if it seems relevant: {url}

Best,
[Your name]"""

    return message.strip()

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

def save_lead_queue(scored_leads: List[Dict[str, Any]], output_path: str = "demo/demo-output/outbound_queue.json"):
    """Save scored leads and outbound queue to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    data = {
        "generated_at": datetime.now().isoformat(),
        "total_leads": len(scored_leads),
        "high_priority": len([l for l in scored_leads if l["priority"] == "high"]),
        "medium_priority": len([l for l in scored_leads if l["priority"] == "medium"]),
        "low_priority": len([l for l in scored_leads if l["priority"] == "low"]),
        "avg_score": sum(l["icp_fit_score"] for l in scored_leads) / len(scored_leads) if scored_leads else 0,
        "leads": scored_leads,
        "demo_mode": True
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✓ Outbound queue saved to {output_path}")

    # Also save markdown summary
    md_path = output_path.replace('.json', '.md')
    save_queue_markdown(data, md_path)

    return output_path

def save_queue_markdown(data: Dict[str, Any], output_path: str):
    """Save human-readable outbound queue markdown."""

    leads = data["leads"]

    md_content = f"""# Warm Outbound Queue

Generated: {data['generated_at']}
**Total Leads:** {data['total_leads']}
**Average ICP Fit:** {data['avg_score']:.1f}/100
**Demo Mode:** {data.get('demo_mode', False)}

## Priority Breakdown
- 🔥 High Priority (80+ score): {data['high_priority']} leads
- 🟡 Medium Priority (60-79): {data['medium_priority']} leads
- 🔵 Low Priority (<60): {data['low_priority']} leads

## Outbound Queue (Priority Order)

"""

    for i, lead in enumerate(leads, 1):
        priority_emoji = "🔥" if lead["priority"] == "high" else "🟡" if lead["priority"] == "medium" else "🔵"

        md_content += f"""### {i}. {lead['name']} - {lead['title']} {priority_emoji}

**Company:** {lead['company']} | **ICP Fit Score:** {lead['icp_fit_score']}/100 | **Priority:** {lead['priority'].title()}
**Source:** {lead['source']}
**Profile:** {lead.get('url', 'N/A')}

**Engagement Context:** {lead['engagement_context']}

**Personalized Message:**
```
{lead['personalized_message']}
```

**Approval Required:** ✅ YES
**Status:** {lead['status']}

---

"""

    md_content += f"""## Outreach Guidelines

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

    with open(output_path, 'w') as f:
        f.write(md_content)

    print(f"✓ Queue markdown saved to {output_path}")

def main():
    """Main lead scoring workflow."""
    print("🎯 Flywheel Agent - Lead Scorer")
    print("Scoring leads and generating warm outbound queue...\n")

    try:
        # Load product profile
        profile = load_product_profile()
        print(f"✓ Loaded profile for {profile['product_name']}")

        # Get leads data
        leads = get_leads_data(profile)
        print(f"✓ Loaded {len(leads)} leads")

        if not leads:
            print("⚠️  No leads found. Add leads.csv or prospects.csv to score leads.")
            return 1

        # Score and personalize leads
        scored_leads = score_and_personalize_leads(leads, profile)

        # Save outbound queue
        output_path = save_lead_queue(scored_leads)

        # Print summary
        print(f"\n📊 Lead Scoring Summary:")
        print(f"   Total Leads: {len(scored_leads)}")
        print(f"   High Priority: {len([l for l in scored_leads if l['priority'] == 'high'])}")
        print(f"   Average Score: {sum(l['icp_fit_score'] for l in scored_leads) / len(scored_leads):.1f}/100")
        print(f"   Top Lead: {scored_leads[0]['name']} ({scored_leads[0]['icp_fit_score']}/100)")

        if profile.get("demo_mode"):
            print("\n🎭 Running in DEMO MODE - using sample lead data")

        print(f"\n✅ Lead scoring complete! Review and approve messages before sending.")
        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Run flywheel_intake.py first to create product profile.")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())