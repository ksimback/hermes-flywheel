#!/usr/bin/env python3
"""
Trend Scanner Script
Generates trend-based content and social media drafts for weekly campaigns.

Trend sources: agent research via --input (key: "trends"), or the bundled
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
    get_proof_points,
    load_profile,
    md_safe,
    out_path,
    resolve_research,
    safe_number,
    write_json,
    write_text,
)

TRENDS_SCHEMA_HINT = (
    "JSON with key 'trends': list of "
    "{trend, platform, volume, relevance, example_post, viral_potential, keywords}"
)

# Sample trends for demo mode
SAMPLE_TRENDS = [
    {
        "trend": "AI replacing traditional tools",
        "platform": "Twitter/X",
        "volume": "high",
        "relevance": "engineering software being disrupted by AI",
        "example_post": "Old school CAD is dying. AI-powered design tools are 10x faster and catch errors humans miss.",
        "viral_potential": 85,
        "keywords": ["AI tools", "traditional software", "productivity", "engineering"]
    },
    {
        "trend": "Open source vs enterprise software",
        "platform": "LinkedIn",
        "volume": "medium",
        "relevance": "debate about open source alternatives to expensive enterprise tools",
        "example_post": "Why pay $50k/year for enterprise software when open source alternatives do 80% of the work?",
        "viral_potential": 72,
        "keywords": ["open source", "enterprise", "cost savings", "alternatives"]
    },
    {
        "trend": "Remote work tooling evolution",
        "platform": "Reddit",
        "volume": "medium",
        "relevance": "engineers discussing best remote collaboration tools",
        "example_post": "What tools actually make remote engineering work? Thread on game-changers vs overhyped solutions.",
        "viral_potential": 68,
        "keywords": ["remote work", "collaboration", "engineering tools", "productivity"]
    },
    {
        "trend": "E-commerce industry growth",
        "platform": "Twitter/X",
        "volume": "high",
        "relevance": "renewed interest in e-commerce analytics and growth automation",
        "example_post": "E-commerce industry is booming but the software is stuck in 1990. Who's building modern tools for e-commerce?",
        "viral_potential": 78,
        "keywords": ["e-commerce industry", "e-commerce", "modern tools", "technology gap"]
    },
    {
        "trend": "No-code/low-code movement",
        "platform": "TikTok",
        "volume": "high",
        "relevance": "non-technical users wanting to build technical solutions",
        "example_post": "POV: You're an engineer but you still use no-code tools because they're faster than building from scratch",
        "viral_potential": 82,
        "keywords": ["no-code", "efficiency", "engineering", "modern workflows"]
    }
]

CONTENT_FORMATS = {
    "twitter_thread": {
        "name": "Twitter/X Thread",
        "max_length": 280,
        "structure": ["hook", "problem", "solution", "proof", "cta"],
        "optimal_length": "5-8 tweets"
    },
    "linkedin_post": {
        "name": "LinkedIn Professional Post",
        "max_length": 3000,
        "structure": ["professional_hook", "industry_insight", "personal_experience", "call_to_action"],
        "optimal_length": "150-300 words"
    },
    "reddit_comment": {
        "name": "Reddit Community Comment",
        "max_length": 10000,
        "structure": ["context_acknowledgment", "personal_story", "helpful_insight", "resource_share"],
        "optimal_length": "100-200 words"
    },
    "tiktok_script": {
        "name": "TikTok Video Script",
        "max_length": 2200,
        "structure": ["hook_3_seconds", "problem_demo", "solution_demo", "results_reveal"],
        "optimal_length": "30-60 seconds"
    },
    "youtube_short": {
        "name": "YouTube Shorts Script",
        "max_length": 2200,
        "structure": ["attention_grabber", "quick_demo", "key_benefit", "where_to_learn_more"],
        "optimal_length": "60 seconds"
    }
}


def normalize_trend(trend: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a trend dict and fill in any fields the templates rely on.

    Research values may carry the wrong types (e.g. a string
    viral_potential); coerce so scoring and templating degrade instead of
    crashing.
    """
    trend = copy.deepcopy(trend)
    trend["trend"] = str(trend.get("trend") or "Untitled trend")
    trend["platform"] = str(trend.get("platform") or "Social")
    trend["volume"] = str(trend.get("volume") or "medium")
    trend["relevance"] = str(trend.get("relevance") or "")
    trend["keywords"] = [str(k) for k in (trend.get("keywords") or [])]
    trend["viral_potential"] = int(safe_number(trend.get("viral_potential", 50), 50))
    if not trend.get("example_post"):
        trend["example_post"] = f"{trend['trend']} is picking up momentum right now."
    else:
        trend["example_post"] = str(trend["example_post"])
    return trend


def get_main_proof(profile: Dict[str, Any]) -> str:
    """First proof point, falling back gracefully when the list is empty.

    Real founder profiles may have no proof points yet (disclaimers live in
    positioning.review_notes, which must never reach content copy).
    """
    proof_points = get_proof_points(profile)
    if proof_points:
        return proof_points[0]
    one_liner = str(profile.get("one_liner", "") or "").strip()
    return one_liner or "a noticeably better workflow"


def identify_relevant_trends(trends: List[Dict[str, Any]], profile: Dict[str, Any],
                             data_source: str) -> List[Dict[str, Any]]:
    """Score trends for relevance to the product and ICP."""

    icp = profile.get("icp", {})
    keywords = [kw.lower() for kw in icp.get("keywords", []) or []]
    pain_points = [pp.lower() for pp in icp.get("pain_points", []) or []]

    # Agent-researched trends were already vetted upstream; only the broad
    # sample fixture gets filtered by the relevance threshold.
    min_score = 50 if data_source == "sample_fixture" else 0

    relevant_trends = []
    for trend in trends:
        trend = normalize_trend(trend)
        score = calculate_trend_relevance(trend, profile, keywords, pain_points)
        if score >= min_score:
            trend["relevance_score"] = score
            trend["product_angle"] = generate_product_angle(trend, profile)
            relevant_trends.append(trend)

    # Sort by relevance and viral potential
    relevant_trends.sort(key=lambda x: (x["relevance_score"] + x["viral_potential"]) / 2, reverse=True)

    return relevant_trends


def calculate_trend_relevance(trend: Dict[str, Any], profile: Dict[str, Any],
                              keywords: List[str], pain_points: List[str]) -> int:
    """Calculate how relevant a trend is to the product (0-100)."""

    score = 0

    trend_text = f"{trend.get('trend', '')} {trend.get('relevance', '')} {' '.join(trend.get('keywords', []))}".lower()
    category = profile.get("category", "").lower()

    # Direct keyword matches
    for keyword in keywords:
        if keyword in trend_text:
            score += 15

    # Pain point matches
    for pain_point in pain_points:
        if any(word in trend_text for word in pain_point.split()):
            score += 10

    # Category matches
    if category and (category in trend_text or any(word in trend_text for word in category.split())):
        score += 20

    # Tool/software relevance
    if "tool" in trend_text or "software" in trend_text:
        score += 15

    # Industry relevance
    if "engineering" in trend_text and "engineering" in category:
        score += 25
    elif "ai" in trend_text and "ai" in category:
        score += 25
    elif "e-commerce" in trend_text and "e-commerce" in category:
        score += 25

    # Viral potential bonus
    viral_potential = safe_number(trend.get("viral_potential", 50), 50)
    if viral_potential > 80:
        score += 10
    elif viral_potential > 70:
        score += 5

    return min(100, score)


def generate_product_angle(trend: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """Generate how to angle the product within this trend."""

    product_name = profile.get("product_name", "Product")
    category = profile.get("category", "software")
    positioning = profile.get("positioning", {}) or {}
    main_claim = positioning.get("primary_claim") or profile.get("one_liner") or "a modern solution"
    current_year = datetime.now().year

    trend_topic = trend.get("trend", "")

    # Generate contextual angle
    if "ai" in trend_topic.lower():
        angle = f"{product_name} represents the AI-native approach to {category} - {main_claim}"
    elif "traditional" in trend_topic.lower() or "old" in trend.get("example_post", "").lower():
        angle = f"While everyone talks about legacy {category} tools, {product_name} shows what modern alternatives look like"
    elif "open source" in trend_topic.lower():
        angle = f"{product_name} proves you don't need enterprise budgets for professional {category} results"
    elif "remote" in trend_topic.lower():
        angle = f"Remote {category} teams need tools built for distributed workflows - {product_name} delivers"
    elif "e-commerce" in trend_topic.lower() and "e-commerce" in category:
        angle = f"The e-commerce industry needs modern tools - {product_name} is what e-commerce intelligence looks like in {current_year}"
    else:
        angle = f"{product_name} exemplifies the trend toward {main_claim.lower()} in {category}"

    return angle


def generate_content_drafts(trends: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate content drafts for each relevant trend."""

    content_drafts = []

    for trend in trends:
        # Generate content for multiple formats
        for format_key, format_config in CONTENT_FORMATS.items():
            content = generate_format_specific_content(
                trend, profile, format_key, format_config
            )

            draft = {
                "trend": trend["trend"],
                "platform": format_config["name"],
                "format": format_key,
                "content": content,
                "trend_relevance": trend["relevance_score"],
                "viral_potential": trend["viral_potential"],
                "product_angle": trend["product_angle"],
                "estimated_reach": estimate_content_reach(format_key, trend),
                "approval_required": True,
                "status": "draft",
                "posting_guidelines": get_posting_guidelines(format_key)
            }

            content_drafts.append(draft)

    # Sort by combined score (relevance + viral potential)
    content_drafts.sort(
        key=lambda x: (x["trend_relevance"] + x["viral_potential"]) / 2,
        reverse=True
    )

    return content_drafts[:15]  # Top 15 content pieces


def generate_format_specific_content(trend: Dict[str, Any], profile: Dict[str, Any],
                                     format_key: str, format_config: Dict[str, Any]) -> str:
    """Generate content specific to platform format."""

    product_name = profile.get("product_name", "Product")
    url = profile.get("url", "")
    one_liner = profile.get("one_liner", "Revolutionary solution")

    main_proof = get_main_proof(profile)

    trend_topic = trend["trend"]
    product_angle = trend["product_angle"]

    if format_key == "twitter_thread":
        content = f"""🧵 Thread: {trend_topic} is reshaping our industry

1/ {trend["example_post"]}

2/ This is exactly what we're seeing in {profile.get('category', 'our e-commerce')}. Legacy solutions are struggling to keep up.

3/ {product_angle}

4/ Early results: {main_proof}

5/ The shift is happening faster than most realize. Tools like {product_name} are just the beginning.

6/ If you're dealing with this transition, worth checking out: {url}

What's your take on this trend? 👇"""

    elif format_key == "linkedin_post":
        content = f"""The {trend_topic} trend is accelerating, and it's creating both challenges and opportunities in {profile.get('category', 'our industry')}.

I've been watching this play out firsthand. {trend["relevance"]}

Here's what I'm seeing:
• Legacy tools are showing their age
• Teams are demanding better UX and performance
• AI-native solutions are setting new expectations

{product_angle}. We've seen {main_proof.lower()}, which validates this approach.

The question isn't whether this trend will continue - it's how quickly organizations will adapt.

For those navigating this transition: {url}

What patterns are you seeing in your industry? #TechTrends #Innovation"""

    elif format_key == "reddit_comment":
        content = f"""This is so true. I've been dealing with {trend_topic.lower()} in my work and it's a real shift.

We actually built {product_name} ({url}) specifically because of this trend. {one_liner}

The results have been interesting - {main_proof.lower()}. But more importantly, it's changed how our team approaches {profile.get('category', 'these problems')}.

{product_angle.replace(product_name + ' ', 'This ').lower()}.

Not trying to sell anything here, just sharing what we learned building in this space. Happy to answer questions if anyone's curious about the technical details."""

    elif format_key == "tiktok_script":
        content = f"""[Hook - 3 seconds]
"POV: {trend_topic} is happening in your industry"

[Problem Demo - 10 seconds]
*Shows old/slow workflow*
"This is how everyone still does {profile.get('category', 'this work')}"

[Solution Demo - 15 seconds]
*Shows {product_name} interface*
"But this is what's possible now: {main_proof.lower()}"

[Results - 10 seconds]
*Shows before/after comparison*
"{product_name} = the future of {profile.get('category', 'this work')}"

[CTA]
"Link in bio to try it yourself"

Text overlay: "{trend_topic} is real" → "{product_name}" → "{main_proof}" → "{url}"
"""

    elif format_key == "youtube_short":
        content = f"""[0-3s] Hook: "{trend_topic} is changing everything in {profile.get('category', 'this industry')}"

[3-15s] Problem: "Most tools weren't built for this new reality"
*Quick montage of old interfaces/workflows*

[15-45s] Solution Demo: "Meet {product_name} - {one_liner}"
*Screen recording of key features*
"{main_proof}"

[45-60s] Results: "This is what modern {profile.get('category', 'workflows')} look like"
*Before/after comparison*

[End screen] "Try it yourself: {url}"

Title: "This Tool is Changing {profile.get('category', 'Everything')}"
Tags: #TechTrends #Innovation #{profile.get('category', 'Software').title()}"""

    else:
        content = f"Content about {trend_topic} featuring {product_name}: {one_liner}"

    return content.strip()


def estimate_content_reach(format_key: str, trend: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate potential reach for content format."""

    viral_potential = safe_number(trend.get("viral_potential", 50), 50)
    base_multiplier = viral_potential / 50  # Scale based on viral potential

    reach_estimates = {
        "twitter_thread": {
            "organic_impressions": int(500 * base_multiplier),
            "engagement_rate": "2-5%",
            "potential_viral_reach": int(5000 * base_multiplier) if viral_potential > 75 else 0
        },
        "linkedin_post": {
            "organic_impressions": int(300 * base_multiplier),
            "engagement_rate": "3-8%",
            "potential_viral_reach": int(3000 * base_multiplier) if viral_potential > 70 else 0
        },
        "reddit_comment": {
            "organic_impressions": int(200 * base_multiplier),
            "engagement_rate": "5-15%",
            "potential_viral_reach": int(2000 * base_multiplier) if viral_potential > 80 else 0
        },
        "tiktok_script": {
            "organic_impressions": int(1000 * base_multiplier),
            "engagement_rate": "8-20%",
            "potential_viral_reach": int(50000 * base_multiplier) if viral_potential > 80 else 0
        },
        "youtube_short": {
            "organic_impressions": int(800 * base_multiplier),
            "engagement_rate": "4-12%",
            "potential_viral_reach": int(10000 * base_multiplier) if viral_potential > 75 else 0
        }
    }

    return reach_estimates.get(format_key, {
        "organic_impressions": int(100 * base_multiplier),
        "engagement_rate": "1-3%",
        "potential_viral_reach": 0
    })


def get_posting_guidelines(format_key: str) -> str:
    """Get platform-specific posting guidelines."""

    guidelines = {
        "twitter_thread": "Post thread during peak hours (12-3pm or 7-9pm EST). Use relevant hashtags. Engage with replies within first hour.",
        "linkedin_post": "Post Tuesday-Thursday 9am-12pm EST. Use professional tone. Include industry hashtags. Respond to comments promptly.",
        "reddit_comment": "Follow community rules. Provide value first, mention product naturally. Don't appear promotional. Engage authentically.",
        "tiktok_script": "Post 6-10am or 7-9pm EST. Use trending sounds when possible. Include captions for accessibility. Engage with comments quickly.",
        "youtube_short": "Post consistently at same time. Use clear thumbnails. Optimize for mobile viewing. Cross-promote on other platforms."
    }

    return guidelines.get(format_key, "Follow platform best practices and community guidelines.")


def save_trend_content(args, content_drafts: List[Dict[str, Any]], trends: List[Dict[str, Any]],
                       profile: Dict[str, Any], data_source: str):
    """Save trend-based content to JSON + markdown."""

    json_path = out_path(args, "trend_content.json")

    data = {
        "generated_at": datetime.now().isoformat(),
        "total_trends": len(trends),
        "total_content_pieces": len(content_drafts),
        "avg_viral_potential": sum(t["viral_potential"] for t in trends) / len(trends) if trends else 0,
        "relevant_trends": trends,
        "content_drafts": content_drafts,
        "product_name": str(profile.get("product_name") or ""),
        "demo_mode": artifact_demo_mode(profile, data_source),
        "data_source": data_source,
    }

    write_json(json_path, data)
    print(f"✓ Trend content saved to {json_path}")

    # Also save markdown summary
    md_path = out_path(args, "trend_content.md")
    save_content_markdown(data, md_path)

    return json_path


def save_content_markdown(data: Dict[str, Any], output_path):
    """Save human-readable trend content markdown."""

    trends = data["relevant_trends"]
    content_drafts = data["content_drafts"]

    md_content = f"""# Weekly Trend Content Strategy

Generated: {data['generated_at']}
**Relevant Trends:** {data['total_trends']}
**Content Pieces:** {data['total_content_pieces']}
**Avg Viral Potential:** {data['avg_viral_potential']:.1f}/100
**Demo Mode:** {data.get('demo_mode', False)}
**Data Source:** {data.get('data_source', 'unknown')}

## Trending Topics (Relevance Order)

"""

    for i, trend in enumerate(trends, 1):
        md_content += f"""### {i}. {md_safe(trend['trend'])} (Score: {trend['relevance_score']}/100)

**Platform:** {md_safe(trend['platform'])} | **Volume:** {md_safe(trend['volume'])} | **Viral Potential:** {trend['viral_potential']}/100

**Relevance:** {md_safe(trend['relevance'])}
**Product Angle:** {md_safe(trend['product_angle'])}

**Example Post:** "{md_safe(trend['example_post'])}"

---

"""

    md_content += """## Content Drafts (Priority Order)

"""

    for i, draft in enumerate(content_drafts, 1):
        reach = draft["estimated_reach"]

        md_content += f"""### {i}. {draft['platform']} - {md_safe(draft['trend'])}

**Format:** {draft['format']} | **Relevance:** {draft['trend_relevance']}/100 | **Viral Potential:** {draft['viral_potential']}/100

**Estimated Reach:** {reach['organic_impressions']:,} impressions | **Engagement Rate:** {reach['engagement_rate']}

**Content:**
```
{md_safe(draft['content'])}
```

**Posting Guidelines:** {draft['posting_guidelines']}

**Approval Required:** ✅ YES
**Status:** {draft['status']}

---

"""

    # Platform summary
    platform_counts = {}
    for draft in content_drafts:
        platform = draft["format"]
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    md_content += f"""## Content Distribution Summary

**By Platform:**
{chr(10).join(f"- {platform.replace('_', ' ').title()}: {count} pieces" for platform, count in platform_counts.items())}

**Total Estimated Reach:** {sum(d['estimated_reach']['organic_impressions'] for d in content_drafts):,} impressions

## Weekly Content Calendar

### Monday: Industry Analysis
- Post LinkedIn professional insights
- Share Twitter threads on industry trends

### Tuesday-Wednesday: Product Integration
- Reddit community participation
- LinkedIn product-trend connections

### Thursday-Friday: Visual Content
- TikTok trend videos
- YouTube Shorts with demos

### Weekend: Engagement & Optimization
- Respond to comments and engagement
- Analyze performance for next week

## Next Steps

1. ✅ Review trend relevance and content fit
2. ⚠️  **Get approval before posting ANY content**
3. 📝 Customize content with current product updates
4. 📅 Schedule posts according to platform optimal times
5. 📊 Set up tracking for engagement and conversions

**SAFETY REMINDER:** All social media posts require explicit approval before publishing.
"""

    write_text(output_path, md_content)

    print(f"✓ Content markdown saved to {output_path}")


def main():
    """Main trend scanning workflow."""
    configure_stdout()
    print("📈 Flywheel Agent - Trend Scanner")
    print("Generating trend-based content for weekly campaigns...\n")

    parser = build_parser("Generate trend-based, approval-gated content drafts.")
    args = parser.parse_args()

    try:
        # Load product profile
        profile = load_profile(args)
        print(f"✓ Loaded profile for {profile.get('product_name', 'unknown product')}")

        # Resolve trend research (--input research > demo fixture > exit 2)
        candidate_trends, data_source = resolve_research(
            args, profile, "trends", TRENDS_SCHEMA_HINT, fixture=SAMPLE_TRENDS
        )

        # Identify relevant trends
        trends = identify_relevant_trends(candidate_trends, profile, data_source)
        print(f"✓ Found {len(trends)} relevant trends ({data_source})")

        if not trends:
            print("⚠️  No relevant trends found for this product category.")
            return EXIT_ERROR

        # Generate content drafts
        content_drafts = generate_content_drafts(trends, profile)
        print(f"✓ Generated {len(content_drafts)} content pieces")

        # Save trend content
        save_trend_content(args, content_drafts, trends, profile, data_source)

        # Print summary
        total_reach = sum(d["estimated_reach"]["organic_impressions"] for d in content_drafts)
        avg_viral = sum(t["viral_potential"] for t in trends) / len(trends) if trends else 0

        print(f"\n📊 Trend Content Summary:")
        print(f"   Content Pieces: {len(content_drafts)}")
        print(f"   Estimated Reach: {total_reach:,} impressions")
        print(f"   Avg Viral Potential: {avg_viral:.1f}/100")
        print(f"   Top Trend: {trends[0]['trend']} ({trends[0]['relevance_score']}/100)")

        if data_source == "sample_fixture":
            print("\n🎭 Running in DEMO MODE - using sample trend data")

        print(f"\n✅ Trend scanning complete! Review and approve content before posting.")
        return EXIT_OK

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Unexpected error: {e}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
