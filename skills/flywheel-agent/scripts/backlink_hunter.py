#!/usr/bin/env python3
"""
Backlink Hunter Script
Ranks competitor backlink and listing opportunities.

Opportunity discovery is research: for real runs the calling agent performs
web research and supplies findings via --input. The bundled sample fixture is
only used in explicit demo mode.
"""

import sys
import traceback
from datetime import datetime
from typing import Dict, List, Any

from _common import (
    EXIT_ERROR,
    EXIT_OK,
    artifact_demo_mode,
    build_parser,
    configure_stdout,
    load_profile,
    md_safe,
    out_path,
    resolve_research,
    write_json,
    write_text,
)

OPPORTUNITY_SCHEMA_HINT = (
    "JSON with key 'opportunities': list of {id, type, source_url, title, "
    "description, why_relevant, estimated_effort, estimated_impact, "
    "recommended_action, outreach_template}"
)

# Defaults applied to agent-supplied items so scoring/formatting never KeyErrors.
OPPORTUNITY_DEFAULTS = {
    "type": "unknown",
    "source_url": "",
    "title": "Untitled opportunity",
    "description": "",
    "why_relevant": "",
    "estimated_effort": "medium",
    "estimated_impact": "medium",
    "recommended_action": "Review opportunity and decide on outreach",
    "outreach_template": "",
    "approval_required": True,
    "status": "new",
}

# Sample backlink opportunities for explicit demo mode only.
# Scores are intentionally absent: score_opportunities() computes them.
SAMPLE_OPPORTUNITIES = [{'id': 'opp_001',
  'type': 'backlink_listing',
  'source_url': 'https://example.com/ecommerce-tools/cartpilot-alternatives',
  'title': 'CartPilot alternatives directory',
  'description': 'Directory of e-commerce analytics and customer intelligence alternatives',
  'why_relevant': 'High-intent directory where e-commerce founders compare customer intelligence '
                  'tools',
  'estimated_effort': 'low',
  'estimated_impact': 'medium',
  'recommended_action': 'Submit ExampleAI as an alternative for early-stage e-commerce teams',
  'outreach_template': 'Hi team,\n'
                       '\n'
                       "I'd like to suggest adding ExampleAI (example.ai) to your e-commerce "
                       'intelligence tools directory.\n'
                       '\n'
                       'ExampleAI helps e-commerce founders turn store and customer signals into '
                       'weekly growth actions. Happy to provide any additional details needed for '
                       'the listing.\n'
                       '\n'
                       'Best regards',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_002',
  'type': 'directory_listing',
  'source_url': 'https://example.com/awesome-ecommerce-tools',
  'title': 'Awesome E-commerce Intelligence Tools',
  'description': 'Curated list of e-commerce analytics, retention, and merchandising tools',
  'why_relevant': 'Curated resource for founders evaluating tools like ExampleAI',
  'estimated_effort': 'low',
  'estimated_impact': 'high',
  'recommended_action': 'Submit PR to add ExampleAI to customer intelligence section',
  'outreach_template': '## ExampleAI\n'
                       '\n'
                       'E-commerce intelligence engine for growth teams.\n'
                       '\n'
                       '- **Link:** https://example.ai\n'
                       '- **Features:** Customer segmentation, campaign opportunity discovery, '
                       'weekly GTM recommendations\n'
                       '- **Use case:** E-commerce founders and growth teams\n'
                       '\n'
                       'Helps teams move from manual store analysis to approval-gated weekly '
                       'growth actions.',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_003',
  'type': 'blog_mention',
  'source_url': 'https://example.com/best-ecommerce-intelligence-tools',
  'title': 'Best E-commerce Intelligence Tools for Founders',
  'description': 'Annual roundup of e-commerce intelligence and analytics tools',
  'why_relevant': "Comparison article where ExampleAI's founder-focused positioning fits",
  'estimated_effort': 'medium',
  'estimated_impact': 'high',
  'recommended_action': 'Pitch ExampleAI for the next e-commerce intelligence roundup',
  'outreach_template': 'Hi editorial team,\n'
                       '\n'
                       'I noticed your roundup of e-commerce intelligence tools. ExampleAI helps '
                       'early-stage e-commerce founders turn store data into weekly acquisition '
                       'actions, with human approval gates before outreach or spend. Would this be '
                       'a fit for a future update?\n'
                       '\n'
                       'Best regards',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_004',
  'type': 'community_mention',
  'source_url': 'https://example.com/community/ecommerce-growth-tools',
  'title': 'E-commerce growth tools discussion',
  'description': 'Founder community thread about analytics and customer intelligence workflows',
  'why_relevant': 'Active conversation where ExampleAI could be mentioned as a lightweight '
                  'intelligence layer',
  'estimated_effort': 'low',
  'estimated_impact': 'medium',
  'recommended_action': 'Participate with a helpful, non-spammy ExampleAI mention',
  'outreach_template': 'For early-stage e-commerce intelligence, ExampleAI is exploring a '
                       'lightweight approach: it turns store and customer signals into a weekly '
                       'GTM sprint instead of another dashboard to babysit. Might be relevant if '
                       "you're trying to prioritize growth actions from messy data.",
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_005',
  'type': 'resource_page',
  'source_url': 'https://example.com/ecommerce-resources/tools',
  'title': 'E-commerce Founder Tools Resource Page',
  'description': 'Resource page listing tools for analytics, retention, and merchandising',
  'why_relevant': 'Good-fit resource page for ExampleAI positioning',
  'estimated_effort': 'medium',
  'estimated_impact': 'medium',
  'recommended_action': 'Request addition to tools list with brief description',
  'outreach_template': 'Hello,\n'
                       '\n'
                       'I found your e-commerce tools resource page and thought ExampleAI might be '
                       'a useful addition. ExampleAI is an e-commerce intelligence engine for '
                       'growth teams that helps founders turn store signals into weekly GTM '
                       'actions. Would you consider adding it?\n'
                       '\n'
                       'Thanks!',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_006',
  'type': 'newsletter_pitch',
  'source_url': 'https://example.com/ecommerce-newsletter',
  'title': 'E-commerce Growth Newsletter',
  'description': 'Newsletter covering growth tools, retention, and merchandising workflows',
  'why_relevant': 'Audience includes e-commerce founders and operators',
  'estimated_effort': 'medium',
  'estimated_impact': 'high',
  'recommended_action': 'Pitch ExampleAI as a lightweight customer intelligence workflow',
  'outreach_template': 'Hi team,\n'
                       '\n'
                       'ExampleAI is an e-commerce intelligence engine for founders who want '
                       'clearer weekly growth actions from store and customer signals. Would this '
                       'fit an upcoming tools or founder workflow roundup?',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_007',
  'type': 'podcast_pitch',
  'source_url': 'https://example.com/growth-podcast',
  'title': 'Growth Operators Podcast',
  'description': 'Podcast covering early-stage growth operations and e-commerce tooling',
  'why_relevant': 'Listeners include founders looking for practical customer acquisition workflows',
  'estimated_effort': 'medium',
  'estimated_impact': 'medium',
  'recommended_action': 'Pitch a founder workflow interview',
  'outreach_template': 'Hi team,\n'
                       '\n'
                       "I'm working on ExampleAI, an e-commerce intelligence engine for growth "
                       'teams. The story is about replacing manual store analysis with weekly, '
                       'approval-gated GTM actions. Could this fit an upcoming founder workflow '
                       'episode?',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_008',
  'type': 'community_mention',
  'source_url': 'https://example.com/community/shopify-founders',
  'title': 'Shopify founders community discussion',
  'description': 'Community thread about prioritizing customer acquisition experiments',
  'why_relevant': 'Relevant place for educational content about customer intelligence workflows',
  'estimated_effort': 'low',
  'estimated_impact': 'medium',
  'recommended_action': 'Draft educational post with ExampleAI as a soft example',
  'outreach_template': "Educational draft only: here's how e-commerce founders can turn messy "
                       'store signals into weekly growth actions. ExampleAI is one lightweight '
                       'approach to this workflow.',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_009',
  'type': 'directory_listing',
  'source_url': 'https://example.com/startups/ecommerce-tools',
  'title': 'E-commerce startup tools ecosystem',
  'description': 'Startup ecosystem research for e-commerce tooling and partnerships',
  'why_relevant': 'Strong source for partnership and customer discovery targets',
  'estimated_effort': 'low',
  'estimated_impact': 'high',
  'recommended_action': 'Build a targeted e-commerce tool prospect list and draft partnership '
                        'outreach',
  'outreach_template': 'Hi {{name}},\n'
                       '\n'
                       "Saw you're building for e-commerce teams. We're building ExampleAI to make "
                       'store intelligence and weekly GTM planning less manual. Would a short demo '
                       'be useful?',
  'approval_required': True,
  'status': 'new'},
 {'id': 'opp_010',
  'type': 'resource_page',
  'source_url': 'https://example.com/customer-intelligence-projects',
  'title': 'Customer Intelligence Related Projects',
  'description': 'Resource page for customer intelligence and e-commerce analytics projects',
  'why_relevant': 'ExampleAI can be positioned as a founder-friendly applied layer for growth '
                  'planning',
  'estimated_effort': 'medium',
  'estimated_impact': 'medium',
  'recommended_action': 'Request inclusion as a related customer intelligence project',
  'outreach_template': 'Hi team,\n'
                       '\n'
                       'Would ExampleAI be appropriate for the related projects page? It is an '
                       'e-commerce intelligence engine that helps founders convert store and '
                       'customer signals into weekly growth actions.',
  'approval_required': True,
  'status': 'new'}]


def prepare_opportunities(items: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize opportunities and personalize outreach templates.

    Works for both fixture items (which reference ExampleAI placeholders) and
    agent-supplied research items (missing optional keys get safe defaults).
    """
    product_name = profile.get("product_name", "YourProduct")
    url = profile.get("url", "")
    domain = url.replace("https://", "").replace("http://", "").strip("/") if url else ""

    prepared = []
    for index, raw in enumerate(items, 1):
        opp = dict(raw)
        for key, default in OPPORTUNITY_DEFAULTS.items():
            opp.setdefault(key, default)
        # Approval gates are clamped, never defaulted: research JSON must not
        # be able to flow through with approval_required: false.
        opp["approval_required"] = True
        if not opp.get("id"):
            opp["id"] = f"opp_{index:03d}"

        # Personalize placeholder product references with the actual product.
        template = opp.get("outreach_template") or ""
        if template:
            if product_name:
                template = template.replace("ExampleAI", product_name)
            if domain:
                template = template.replace("example.ai", domain)
            opp["outreach_template"] = template

        prepared.append(opp)

    return prepared


def score_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Score and rank opportunities by potential impact."""

    for opp in opportunities:
        score = 50  # Base score

        # Impact scoring
        impact = opp.get("estimated_impact", "medium")
        impact_scores = {"low": 0, "medium": 15, "high": 25}
        score += impact_scores.get(impact, 15)

        # Effort scoring (lower effort = higher score)
        effort = opp.get("estimated_effort", "medium")
        effort_scores = {"low": 20, "medium": 10, "high": 5}
        score += effort_scores.get(effort, 10)

        # Type scoring
        type_scores = {
            "directory_listing": 20,
            "backlink_listing": 15,
            "blog_mention": 10,
            "community_mention": 8,
            "resource_page": 12
        }
        opp_type = opp.get("type", "")
        score += type_scores.get(opp_type, 5)

        opp["score"] = min(100, score)

    # Sort by score descending
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    return opportunities


def save_opportunities(opportunities: List[Dict[str, Any]], args, profile: Dict[str, Any], data_source: str):
    """Save opportunities JSON and markdown under the configured output dir."""

    data = {
        "generated_at": datetime.now().isoformat(),
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
        "product_name": str(profile.get("product_name") or ""),
        "demo_mode": artifact_demo_mode(profile, data_source),
        "data_source": data_source
    }

    json_path = write_json(out_path(args, "backlink_opportunities.json"), data)
    print(f"✓ Backlink opportunities saved to {json_path}")

    # Also save markdown summary
    save_opportunities_markdown(data, out_path(args, "backlink_opportunities.md"))

    return json_path


def save_opportunities_markdown(data: Dict[str, Any], output_path):
    """Save human-readable opportunities markdown."""

    opportunities = data["opportunities"]

    md_content = f"""# Backlink & Listing Opportunities

Generated: {data['generated_at']}
**Total Opportunities:** {data['total_opportunities']}
**Demo Mode:** {data.get('demo_mode', False)}

## Top Opportunities (Priority Order)

"""

    for i, opp in enumerate(opportunities, 1):
        md_content += f"""### {i}. {md_safe(opp['title'])} (Score: {opp['score']})

**Type:** {md_safe(opp['type'])} | **Effort:** {md_safe(opp['estimated_effort'])} | **Impact:** {md_safe(opp['estimated_impact'])}
**URL:** {md_safe(opp['source_url'])}

**Why Relevant:** {md_safe(opp['why_relevant'])}

**Recommended Action:** {md_safe(opp['recommended_action'])}

**Outreach Template:**
```
{md_safe(opp['outreach_template'])}
```

**Approval Required:** ✅ YES
**Status:** {opp['status']}

---

"""

    # Summary stats
    effort_counts = {}
    impact_counts = {}
    type_counts = {}

    for opp in opportunities:
        effort = str(opp.get('estimated_effort', 'unknown'))
        impact = str(opp.get('estimated_impact', 'unknown'))
        opp_type = str(opp.get('type', 'unknown'))

        effort_counts[effort] = effort_counts.get(effort, 0) + 1
        impact_counts[impact] = impact_counts.get(impact, 0) + 1
        type_counts[opp_type] = type_counts.get(opp_type, 0) + 1

    md_content += f"""## Summary Statistics

**By Effort Level:**
{chr(10).join(f"- {effort.title()}: {count}" for effort, count in effort_counts.items())}

**By Impact Level:**
{chr(10).join(f"- {impact.title()}: {count}" for impact, count in impact_counts.items())}

**By Opportunity Type:**
{chr(10).join(f"- {opp_type.replace('_', ' ').title()}: {count}" for opp_type, count in type_counts.items())}

## Next Steps

1. ✅ Review opportunities and select top 5-10 to pursue
2. ⚠️  **Get approval before sending any outreach messages**
3. 📝 Customize outreach templates with specific details
4. 📅 Schedule outreach over 2-3 weeks to avoid spam appearance
5. 📊 Track responses and successful listings

**SAFETY REMINDER:** All outreach requires explicit human approval before sending.
"""

    write_text(output_path, md_content)
    print(f"✓ Opportunities markdown saved to {output_path}")


def main():
    """Main backlink hunter workflow."""
    configure_stdout()

    print("🔗 Flywheel Agent - Backlink Hunter")
    print("Finding competitor backlinks and listing opportunities...\n")

    try:
        parser = build_parser("Rank backlink and listing opportunities for the product.")
        args = parser.parse_args()

        # Load product profile
        profile = load_profile(args)
        print(f"✓ Loaded profile for {profile['product_name']}")

        # Agent research via --input, or the sample fixture in explicit demo
        # mode. Real runs without research exit with EXIT_MISSING_INPUT.
        items, data_source = resolve_research(
            args, profile, "opportunities", OPPORTUNITY_SCHEMA_HINT,
            fixture=SAMPLE_OPPORTUNITIES,
        )

        opportunities = prepare_opportunities(items, profile)
        print(f"✓ Found {len(opportunities)} potential opportunities")

        # Score and rank opportunities
        scored_opportunities = score_opportunities(opportunities)

        # Save results
        save_opportunities(scored_opportunities, args, profile, data_source)

        # Print summary
        print(f"\n📊 Backlink Hunt Summary:")
        print(f"   Total Opportunities: {len(scored_opportunities)}")
        print(f"   Top Opportunity: {scored_opportunities[0]['title']} (Score: {scored_opportunities[0]['score']})")
        print(f"   High Impact: {len([o for o in scored_opportunities if o.get('estimated_impact') == 'high'])}")
        print(f"   Low Effort: {len([o for o in scored_opportunities if o.get('estimated_effort') == 'low'])}")

        if data_source == "sample_fixture":
            print("\n🎭 Running in DEMO MODE - using sample opportunity data")

        print(f"\n✅ Backlink hunt complete! Review and approve outreach before sending.")
        return EXIT_OK

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Unexpected error: {e}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
