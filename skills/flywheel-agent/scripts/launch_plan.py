#!/usr/bin/env python3
"""
Launch Plan Generator
Creates comprehensive launch strategy across multiple channels.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

LAUNCH_CHANNELS = {
    "product_hunt": {
        "name": "Product Hunt",
        "category": "launch_platform",
        "effort": "high",
        "timeline": "1-2 weeks prep",
        "requirements": ["product screenshots", "GIF demo", "maker account", "hunter network"],
        "copy_template": "🚀 Introducing {product_name} - {one_liner}\n\n✨ What makes it special:\n{proof_points}\n\n🎯 Perfect for {icp_buyer} who need {main_pain_point}\n\nCheck it out and let us know what you think! 👇",
        "success_metrics": ["upvotes", "comments", "traffic", "signups"]
    },
    "hacker_news": {
        "name": "Hacker News",
        "category": "community",
        "effort": "medium",
        "timeline": "same day",
        "requirements": ["technical angle", "HN account with karma", "launch timing"],
        "copy_template": "Show HN: {product_name} – {one_liner}\n\nWe built this because {main_pain_point} was a constant frustration for {icp_buyer}. {proof_points[0]}.\n\nWould love feedback from the HN community on our approach!",
        "success_metrics": ["points", "comments", "technical discussion"]
    },
    "indie_hackers": {
        "name": "Indie Hackers",
        "category": "community",
        "effort": "medium",
        "timeline": "1 week",
        "requirements": ["founder story", "IH account", "metrics/traction"],
        "copy_template": "🛠️ Just launched {product_name} after 6 months of building\n\nThe problem: {main_pain_point}\nOur solution: {one_liner}\n\nTraction so far: [your metrics here]\n\nWhat would you want to see next? 🤔",
        "success_metrics": ["engagement", "followers", "networking"]
    },
    "reddit_communities": {
        "name": "Reddit Communities",
        "category": "community",
        "effort": "medium",
        "timeline": "ongoing",
        "requirements": ["relevant subreddits", "authentic participation", "value-first posts"],
        "copy_template": "Built a tool to solve {main_pain_point} - would love feedback\n\nAs a {icp_buyer}, I kept running into {main_pain_point}. Existing solutions were {competitor_weakness}.\n\nSo I built {product_name}: {one_liner}\n\nStill early but {proof_points[0]}. Happy to share more details if useful!",
        "success_metrics": ["upvotes", "comments", "community engagement"]
    },
    "betalist": {
        "name": "BetaList",
        "category": "directory",
        "effort": "low",
        "timeline": "1 day",
        "requirements": ["beta/early access", "signup page", "screenshots"],
        "copy_template": "{product_name} - {one_liner}\n\nEarly access for {icp_buyer} who want to {main_benefit}. {proof_points[0]}.\n\n🎯 Perfect for: {icp_description}\n💡 Key features: [list 3-4 features]\n🚀 Coming soon: [roadmap items]",
        "success_metrics": ["beta signups", "email subscribers"]
    },
    "devhunt": {
        "name": "DevHunt",
        "category": "directory",
        "effort": "low",
        "timeline": "1 day",
        "requirements": ["developer tool angle", "technical screenshots", "GitHub link"],
        "copy_template": "{product_name} - {one_liner}\n\nOpen source tool for {icp_buyer}. Built because {main_pain_point} was holding back our {category} projects.\n\n🔧 Tech stack: [your stack]\n📦 Installation: [install method]\n🌟 GitHub: [repo link]",
        "success_metrics": ["developer signups", "GitHub stars"]
    },
    "peerlist": {
        "name": "Peerlist",
        "category": "professional",
        "effort": "low",
        "timeline": "1 day",
        "requirements": ["professional profile", "project showcase", "network"],
        "copy_template": "Excited to share {product_name} with the Peerlist community! 🎉\n\n{one_liner}\n\nBuilt for {icp_buyer} who {main_pain_point}. {proof_points[0]}.\n\nWould love to connect with others building in the {category} e-commerce!",
        "success_metrics": ["professional connections", "project views"]
    },
    "micro_communities": {
        "name": "Micro Communities",
        "category": "niche",
        "effort": "high",
        "timeline": "2-4 weeks",
        "requirements": ["niche identification", "community research", "relationship building"],
        "copy_template": "Hey {community_name}! 👋\n\nNoticed a lot of discussions about {main_pain_point} here. We just built something that might help: {product_name}.\n\n{one_liner}\n\nWould love to get feedback from this community since you're dealing with these challenges daily. Happy to offer early access!",
        "success_metrics": ["community engagement", "niche adoption"]
    }
}

def load_product_profile(path: str = "data/product_profile.json") -> Dict[str, Any]:
    """Load product profile from JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Product profile not found at {path}. Run flywheel_intake.py first.")

    with open(path, 'r') as f:
        return json.load(f)

def generate_channel_plan(profile: Dict[str, Any], channel_key: str, channel_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate launch plan for a specific channel."""

    # Extract profile data for templating
    product_name = profile.get("product_name", "YourProduct")
    one_liner = profile.get("one_liner", "Revolutionary software solution")
    icp = profile.get("icp", {})
    icp_buyer = icp.get("buyer", "professional")
    icp_buyer_plural = icp_buyer if icp_buyer.endswith("s") else f"{icp_buyer}s"
    pain_points = icp.get("pain_points", ["generic problem"])
    main_pain_point = pain_points[0] if pain_points else "workflow inefficiency"
    proof_points = profile.get("positioning", {}).get("proof_points", ["Significant improvement over alternatives"])

    # Generate copy from template
    copy_template = channel_config.get("copy_template", "Check out {product_name}!")

    try:
        generated_copy = copy_template.format(
            product_name=product_name,
            one_liner=one_liner,
            icp_buyer=icp_buyer_plural,
            main_pain_point=main_pain_point,
            proof_points=proof_points,
            main_benefit=f"solve {main_pain_point}",
            icp_description=f"{icp_buyer_plural} working with {profile.get('category', 'software')}",
            category=profile.get("category", "software"),
            community_name="[Community Name]"
        )
    except KeyError as e:
        # Fallback if template variables missing
        generated_copy = f"Introducing {product_name} - {one_liner}\n\nBuilt for {icp_buyer_plural} who need better solutions for {main_pain_point}."

    return {
        "channel": channel_key,
        "name": channel_config["name"],
        "category": channel_config["category"],
        "effort": channel_config["effort"],
        "timeline": channel_config["timeline"],
        "requirements": channel_config["requirements"],
        "copy": generated_copy,
        "success_metrics": channel_config["success_metrics"],
        "approval_required": True,  # All launch actions require approval
        "status": "draft",
        "priority_score": calculate_channel_priority(profile, channel_config)
    }

def calculate_channel_priority(profile: Dict[str, Any], channel_config: Dict[str, Any]) -> int:
    """Calculate priority score for channel (1-100)."""
    base_score = 50

    # Adjust based on effort (lower effort = higher priority for MVP)
    effort_scores = {"low": 20, "medium": 10, "high": 0}
    effort = channel_config.get("effort", "medium")
    base_score += effort_scores.get(effort, 0)

    # Adjust based on category fit
    category = profile.get("category", "")
    if "software" in category or "ai" in category:
        if channel_config["name"] in ["Hacker News", "DevHunt"]:
            base_score += 15

    # Boost directories for easy wins
    if channel_config["category"] == "directory":
        base_score += 10

    return min(100, base_score)

def generate_launch_plan(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete launch plan across all channels."""

    plan = {
        "product_name": profile["product_name"],
        "generated_at": datetime.now().isoformat(),
        "launch_channels": [],
        "timeline": {},
        "asset_requirements": set(),
        "total_estimated_effort": 0,
        "demo_mode": profile.get("demo_mode", False)
    }

    # Generate plan for each channel
    for channel_key, channel_config in LAUNCH_CHANNELS.items():
        channel_plan = generate_channel_plan(profile, channel_key, channel_config)
        plan["launch_channels"].append(channel_plan)

        # Collect asset requirements
        for req in channel_config["requirements"]:
            plan["asset_requirements"].add(req)

    # Sort channels by priority
    plan["launch_channels"].sort(key=lambda x: x["priority_score"], reverse=True)

    # Convert set to list for JSON serialization
    plan["asset_requirements"] = list(plan["asset_requirements"])

    # Generate timeline recommendations
    plan["timeline"] = generate_launch_timeline(plan["launch_channels"])

    return plan

def generate_launch_timeline(channels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate recommended launch timeline."""

    timeline = {
        "week_1": {
            "focus": "Preparation & Easy Wins",
            "channels": [],
            "tasks": ["Prepare assets", "Set up accounts", "Write copy"]
        },
        "week_2": {
            "focus": "Major Platform Launches",
            "channels": [],
            "tasks": ["Product Hunt launch", "HN submission", "Community posts"]
        },
        "week_3": {
            "focus": "Community Engagement",
            "channels": [],
            "tasks": ["Reddit communities", "Niche outreach", "Follow-up"]
        },
        "ongoing": {
            "focus": "Sustained Engagement",
            "channels": [],
            "tasks": ["Community participation", "Content creation", "Relationship building"]
        }
    }

    # Distribute channels based on effort and timeline
    for channel in channels:
        effort = channel["effort"]
        if effort == "low":
            timeline["week_1"]["channels"].append(channel["name"])
        elif effort == "medium":
            timeline["week_2"]["channels"].append(channel["name"])
        else:
            timeline["week_3"]["channels"].append(channel["name"])

    return timeline

def save_launch_plan(plan: Dict[str, Any], output_path: str = "demo/demo-output/launch_plan.json"):
    """Save launch plan to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(plan, f, indent=2)

    print(f"✓ Launch plan saved to {output_path}")

    # Also save markdown summary
    md_path = output_path.replace('.json', '.md')
    save_launch_plan_markdown(plan, md_path)

    return output_path

def save_launch_plan_markdown(plan: Dict[str, Any], output_path: str):
    """Save human-readable launch plan markdown."""

    md_content = f"""# Launch Plan: {plan['product_name']}

Generated: {plan['generated_at']}

## Executive Summary

**Total Channels:** {len(plan['launch_channels'])}
**Asset Requirements:** {len(plan['asset_requirements'])} unique items
**Demo Mode:** {plan.get('demo_mode', False)}

## Launch Channels (Priority Order)

"""

    for i, channel in enumerate(plan['launch_channels'], 1):
        md_content += f"""### {i}. {channel['name']} (Score: {channel['priority_score']})

**Category:** {channel['category']} | **Effort:** {channel['effort']} | **Timeline:** {channel['timeline']}

**Requirements:**
{chr(10).join(f"- {req}" for req in channel['requirements'])}

**Copy:**
```
{channel['copy']}
```

**Success Metrics:** {', '.join(channel['success_metrics'])}
**Approval Required:** ✅ YES

---

"""

    md_content += f"""## Asset Requirements Checklist

{chr(10).join(f"- [ ] {asset}" for asset in sorted(plan['asset_requirements']))}

## Launch Timeline

"""

    for period, details in plan['timeline'].items():
        md_content += f"""### {period.replace('_', ' ').title()}
**Focus:** {details['focus']}
**Channels:** {', '.join(details['channels'])}
**Tasks:** {', '.join(details['tasks'])}

"""

    md_content += """## Next Steps

1. ✅ Review channel priorities and copy
2. ⚠️  **Get approval for each launch channel before posting**
3. 📋 Complete asset requirements checklist
4. 🗓️ Schedule launches according to timeline
5. 📊 Set up tracking for success metrics

**SAFETY REMINDER:** All launches require explicit human approval before execution.
"""

    with open(output_path, 'w') as f:
        f.write(md_content)

    print(f"✓ Launch plan markdown saved to {output_path}")

def main():
    """Main launch plan generation workflow."""
    print("🚀 Flywheel Agent - Launch Plan Generator")
    print("Creating comprehensive launch strategy...\n")

    try:
        # Load product profile
        profile = load_product_profile()
        print(f"✓ Loaded profile for {profile['product_name']}")

        # Generate launch plan
        plan = generate_launch_plan(profile)

        # Save plan
        output_path = save_launch_plan(plan)

        # Print summary
        print(f"\n📊 Launch Plan Summary:")
        print(f"   Channels: {len(plan['launch_channels'])}")
        print(f"   Asset Requirements: {len(plan['asset_requirements'])}")
        print(f"   Top Priority: {plan['launch_channels'][0]['name']} (Score: {plan['launch_channels'][0]['priority_score']})")

        if plan.get("demo_mode"):
            print("\n🎭 Running in DEMO MODE")

        print(f"\n✅ Launch plan complete! Review and approve channels before execution.")
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