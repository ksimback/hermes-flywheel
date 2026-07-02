#!/usr/bin/env python3
"""
Sprint Report Generator
Compiles all GTM activities into a comprehensive weekly flywheel sprint report.
"""

import json
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from _common import (
    EXIT_ERROR,
    EXIT_OK,
    ROOT,
    anchor,
    build_parser,
    configure_stdout,
    load_profile,
    out_path,
    write_json,
    write_text,
)
import sprint_ledger as ledger


def load_json_safely(path) -> Optional[Dict[str, Any]]:
    """Load JSON file safely, return None if not found."""
    try:
        path = anchor(path)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  Warning: Could not load {path}: {e}")
    return None


def artifact_ref(path):
    """Reference an artifact relative to the repo root when possible."""
    path = anchor(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)

def generate_executive_summary(profile: Dict[str, Any], all_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate executive summary of the weekly sprint."""

    launch_plan = all_data.get("launch_plan", {})
    opportunities = all_data.get("backlink_opportunities", {})
    leads = all_data.get("outbound_queue", {})
    creator_campaign = all_data.get("creator_campaign", {})
    trend_content = all_data.get("trend_content", {})
    mpp_spend_cards = all_data.get("mpp_spend_cards", {})

    # Calculate totals
    total_launch_channels = len(launch_plan.get("launch_channels", []))
    total_opportunities = opportunities.get("total_opportunities", 0)
    total_leads = leads.get("total_leads", 0)
    total_creator_proposals = creator_campaign.get("total_proposals", 0)
    total_content_pieces = trend_content.get("total_content_pieces", 0)

    # Budget analysis
    budget = profile.get("budget", {})
    weekly_budget = budget.get("weekly_usd", 100)
    max_single_spend = budget.get("max_single_spend_usd", 25)

    creator_budget = creator_campaign.get("total_budget", 0)
    creator_upfront = sum(req.get("amount_usd", 0) for req in creator_campaign.get("spend_requests", []))
    mpp_cards = mpp_spend_cards.get("spend_cards", [])
    mpp_pending_amount = mpp_spend_cards.get("total_pending_amount_usd", sum(card.get("amount_usd", 0) for card in mpp_cards))

    # Priority actions
    high_priority_actions = []

    if launch_plan.get("launch_channels"):
        top_channel = launch_plan["launch_channels"][0]
        high_priority_actions.append({
            "type": "launch",
            "action": f"Launch on {top_channel['name']}",
            "priority": top_channel.get("priority_score", 0),
            "effort": top_channel.get("effort", "medium"),
            "timeline": top_channel.get("timeline", "1 week")
        })

    if opportunities.get("opportunities"):
        top_opp = opportunities["opportunities"][0]
        high_priority_actions.append({
            "type": "backlink",
            "action": f"Outreach to {top_opp['title'][:50]}...",
            "priority": top_opp.get("score", 0),
            "effort": top_opp.get("estimated_effort", "medium"),
            "timeline": "1-2 days"
        })

    if leads.get("leads"):
        high_priority_lead = next((l for l in leads["leads"] if l.get("priority") == "high"), None)
        if high_priority_lead:
            high_priority_actions.append({
                "type": "outbound",
                "action": f"Message {high_priority_lead['name']} at {high_priority_lead['company']}",
                "priority": high_priority_lead.get("icp_fit_score", 0),
                "effort": "low",
                "timeline": "same day"
            })

    if creator_campaign.get("campaign_proposals"):
        top_creator = creator_campaign["campaign_proposals"][0]
        high_priority_actions.append({
            "type": "creator",
            "action": f"Partner with {top_creator['creator']} for {top_creator['campaign_type']}",
            "priority": top_creator.get("relevance_score", 0),
            "effort": "high",
            "timeline": top_creator.get("timeline", "2 weeks")
        })

    if mpp_cards:
        top_card = mpp_cards[0]
        high_priority_actions.append({
            "type": "mpp_spend",
            "action": f"Approve MPP spend card for {top_card.get('resource_name', 'paid GTM resource')}",
            "priority": 92,
            "effort": "low",
            "timeline": "after sprint finalization"
        })

    # Sort by priority
    high_priority_actions.sort(key=lambda x: x["priority"], reverse=True)

    summary = {
        "sprint_week": datetime.now().strftime("Week of %B %d, %Y"),
        "product_name": profile.get("product_name", "Product"),
        "total_actions": (
            total_launch_channels + total_opportunities + total_leads
            + total_creator_proposals + total_content_pieces + len(mpp_cards)
        ),
        "total_content_pieces": total_content_pieces,
        "budget_analysis": {
            "weekly_budget": weekly_budget,
            "max_single_spend_usd": max_single_spend,
            "creator_spend_proposed": creator_upfront,
            "mpp_pending_amount": mpp_pending_amount,
            "creator_total_budget": creator_budget,
            "budget_utilization": round((creator_upfront / weekly_budget) * 100, 1) if weekly_budget > 0 else 0,
            "within_budget": creator_upfront <= weekly_budget
        },
        "channel_breakdown": {
            "launch_channels": total_launch_channels,
            "backlink_opportunities": total_opportunities,
            "warm_leads": total_leads,
            "creator_partnerships": total_creator_proposals,
            "mpp_spend_cards": len(mpp_cards)
        },
        "top_5_actions": high_priority_actions[:5],
        "approval_gates": calculate_approval_gates(all_data),
        "estimated_weekly_impact": estimate_weekly_impact(all_data),
        "demo_mode": profile.get("demo_mode", False)
    }

    return summary

def calculate_approval_gates(all_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate what needs human approval."""

    gates = {
        "outbound_messages": 0,
        "spend_requests": 0,
        "mpp_spend_cards": 0,
        "content_posts": 0,
        "total_spend_amount": 0,
        "mpp_pending_amount": 0
    }

    # Count outbound messages
    leads = all_data.get("outbound_queue", {}).get("leads", [])
    gates["outbound_messages"] = len([l for l in leads if l.get("approval_required", True)])

    opportunities = all_data.get("backlink_opportunities", {}).get("opportunities", [])
    gates["outbound_messages"] += len([o for o in opportunities if o.get("approval_required", True)])

    # Count spend requests
    spend_requests = all_data.get("creator_campaign", {}).get("spend_requests", [])
    mpp_cards = all_data.get("mpp_spend_cards", {}).get("spend_cards", [])
    gates["spend_requests"] = len(spend_requests)
    gates["mpp_spend_cards"] = len(mpp_cards)
    gates["total_spend_amount"] = sum(req.get("amount_usd", 0) for req in spend_requests)
    gates["mpp_pending_amount"] = sum(card.get("amount_usd", 0) for card in mpp_cards)

    # Count content posts
    content_drafts = all_data.get("trend_content", {}).get("content_drafts", [])
    gates["content_posts"] = len([c for c in content_drafts if c.get("approval_required", True)])

    return gates

def estimate_weekly_impact(all_data: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate potential weekly impact metrics."""

    # Launch channel estimates
    launch_channels = all_data.get("launch_plan", {}).get("launch_channels", [])
    estimated_launch_traffic = len(launch_channels) * 150  # Conservative estimate per channel

    # Backlink opportunity estimates
    opportunities = all_data.get("backlink_opportunities", {}).get("opportunities", [])
    high_impact_opps = len([o for o in opportunities if o.get("estimated_impact") == "high"])
    estimated_backlink_traffic = high_impact_opps * 50  # Conservative monthly traffic per high-impact backlink

    # Outbound estimates
    leads = all_data.get("outbound_queue", {}).get("leads", [])
    high_priority_leads = len([l for l in leads if l.get("priority") == "high"])
    estimated_outbound_responses = int(high_priority_leads * 0.15)  # 15% response rate

    # Content estimates
    content_drafts = all_data.get("trend_content", {}).get("content_drafts", [])
    total_estimated_reach = sum(c.get("estimated_reach", {}).get("organic_impressions", 0) for c in content_drafts)

    # Creator estimates
    creator_proposals = all_data.get("creator_campaign", {}).get("campaign_proposals", [])
    total_creator_followers = sum(p.get("followers", 0) for p in creator_proposals)
    estimated_creator_reach = int(total_creator_followers * 0.1)  # 10% reach rate

    return {
        "estimated_weekly_traffic": estimated_launch_traffic + (estimated_backlink_traffic // 4),  # Monthly backlinks divided by 4
        "estimated_outbound_responses": estimated_outbound_responses,
        "estimated_content_reach": total_estimated_reach,
        "estimated_creator_reach": estimated_creator_reach,
        "total_potential_reach": total_estimated_reach + estimated_creator_reach,
        "confidence_level": "illustrative"  # Planning illustrations, not forecasts
    }

SECTION_FOCUS = {
    "launch": ("Execute approved launch channels", "Monitor launch performance and engagement"),
    "backlinks": ("Follow up on backlink outreach responses", "Submit to approved directories and listings"),
    "outbound": ("Execute approved outbound messages", "Follow up with non-responders after 1 week"),
    "content": ("Publish approved trend-based content", "Engage with comments and track performance"),
    "creator": ("Finalize creator partnerships and content briefs", "Provide product access and assets to creators"),
}

# Which artifact presence implies which section is live this week.
SECTION_ARTIFACT = {
    "launch": "launch_plan",
    "backlinks": "backlink_opportunities",
    "outbound": "outbound_queue",
    "content": "trend_content",
    "creator": "creator_campaign",
}


def generate_next_week_plan(profile: Dict[str, Any], all_data: Dict[str, Any],
                            learning: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Plan next week, ordering focus by what the founder actually approves.

    With no history this behaves like the original (focus follows whatever
    was generated). Once prior sprints exist, sections the founder keeps
    approving lead the focus list and sections they keep rejecting are flagged
    for pruning -- the compounding "flywheel" the product promises.
    """
    learning = learning or {"has_history": False}

    next_week = {
        "week": (datetime.now() + timedelta(days=7)).strftime("Week of %B %d, %Y"),
        "focus_areas": [],
        "follow_up_actions": [],
        "optimization_opportunities": [],
        "compound_learning": [],
        "based_on": "prior_sprint_approvals" if learning.get("has_history") else "current_sprint_only",
    }

    live_sections = [sec for sec, art in SECTION_ARTIFACT.items() if all_data.get(art)]

    # Order the live sections: prioritized (high past approval) first, then
    # untested, then deprioritized (repeatedly rejected) last.
    prioritize = learning.get("prioritize_sections", [])
    deprioritize = learning.get("deprioritize_sections", [])
    ordered = (
        [s for s in prioritize if s in live_sections]
        + [s for s in live_sections if s not in prioritize and s not in deprioritize]
        + [s for s in deprioritize if s in live_sections]
    )
    for sec in ordered:
        focus, follow = SECTION_FOCUS[sec]
        next_week["focus_areas"].append(focus)
        next_week["follow_up_actions"].append(follow)

    if learning.get("has_history"):
        last = learning.get("last_sprint") or {}
        next_week["vs_last_sprint"] = {
            "prior_sprints": learning.get("prior_sprints", 0),
            "last_approved": last.get("approved", 0),
            "last_rejected": last.get("rejected", 0),
            "last_executed": last.get("executed", 0),
            "last_approved_spend_usd": last.get("approved_spend_usd", 0),
        }
        next_week["opportunity_scores"] = learning.get("opportunity_scores", {})
        for sec in prioritize:
            next_week["compound_learning"].append(
                f"Keep leaning into '{sec}': high past approval rate."
            )
        for sec in deprioritize:
            next_week["compound_learning"].append(
                f"Propose less '{sec}': the founder keeps rejecting it."
            )

    next_week["optimization_opportunities"] = [
        "A/B test different outbound message templates",
        "Track which launch channels drive highest quality traffic",
        "Measure creator campaign performance vs other channels",
        "Identify trending topics for next week's content",
    ]
    if not learning.get("has_history"):
        next_week["compound_learning"].append(
            "First sprint: approvals recorded now become next week's channel priorities."
        )

    return next_week

def build_review_sections(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the default Slack draft-review dashboard sections."""
    gates = summary.get("approval_gates", {})
    breakdown = summary.get("channel_breakdown", {})
    return [
        {
            "id": "launch",
            "label": "Launch channels",
            "status": "draft",
            "review_command": "review launch",
            "approve_command": "approve launch",
            "edit_command": "edit launch: <change>",
            "summary": f"{breakdown.get('launch_channels', 0)} launch channels drafted"
        },
        {
            "id": "backlinks",
            "label": "Backlink/listing opportunities",
            "status": "draft",
            "review_command": "review backlinks",
            "approve_command": "approve backlinks",
            "edit_command": "edit backlinks: <change>",
            "summary": f"{breakdown.get('backlink_opportunities', 0)} backlink/listing opportunities drafted"
        },
        {
            "id": "outbound",
            "label": "Outbound targets",
            "status": "draft",
            "review_command": "review outbound",
            "approve_command": "approve outbound",
            "edit_command": "edit outbound: <change>",
            "summary": f"{breakdown.get('warm_leads', 0)} warm leads / {gates.get('outbound_messages', 0)} outreach items require later execution approval"
        },
        {
            "id": "content",
            "label": "Content plan",
            "status": "draft",
            "review_command": "review content",
            "approve_command": "approve content",
            "edit_command": "edit content: <change>",
            "summary": f"{summary.get('total_content_pieces', 0)} content drafts"
        },
        {
            "id": "mpp-spend",
            "label": "Stripe MPP spend cards",
            "status": "draft",
            "review_command": "review mpp spend",
            "approve_command": "approve mpp spend",
            "edit_command": "edit mpp spend: <change>",
            "summary": f"{gates.get('mpp_spend_cards', 0)} MPP spend cards / ${gates.get('mpp_pending_amount', 0)} pending for paid GTM resources"
        },
        {
            "id": "budget",
            "label": "Budget/spend gates",
            "status": "draft",
            "review_command": "review budget",
            "approve_command": "approve budget",
            "edit_command": "edit budget: <change>",
            "summary": f"${gates.get('total_spend_amount', 0)} proposed spend across {gates.get('spend_requests', 0)} requests"
        }
    ]


def build_help_catalog() -> Dict[str, Any]:
    """Return the Flywheel command/capability help catalog for chat surfaces."""
    return {
        "trigger_commands": ["help", "what can you do?", "commands", "capabilities"],
        "headline": "Flywheel is your GTM employee for weekly acquisition sprints.",
        "capabilities": [
            "Draft weekly GTM sprints from product, ICP, competitor, budget, and focus context.",
            "Find launch channels and package launch copy/assets.",
            "Identify backlink/listing opportunities from competitor/category research.",
            "Score warm outbound targets and draft approval-gated messages.",
            "Plan creator campaigns and approval-gated spend requests.",
            "Turn paid GTM resources into Stripe MPP spend cards with founder approval commands and test receipts.",
            "Generate trend-based content drafts for social distribution.",
            "Walk users through a draft sprint section by section before finalization."
        ],
        "start_prompts": [
            "Run a GTM sprint for <product>. ICP: <buyer>. Competitors: <names>. Budget: <$>. Focus: <channels>.",
            "Draft a launch sprint for <product/url> targeting <ICP>.",
            "Help me review this sprint step by step."
        ],
        "review_commands": [
            "review launch",
            "review backlinks",
            "review outbound",
            "review content",
            "review mpp spend",
            "review budget",
            "start walkthrough",
            "approve <section>",
            "edit <section>: <change>",
            "finalize sprint",
            "show approvals"
        ],
        "safety_rules": [
            "Draft approvals are plan approvals only, not execution approvals.",
            "No outbound messages, social posts, or spend execute automatically.",
            "Stripe MPP cards are payment approvals only after sprint finalization; autonomous spend is $0.",
            "Execution approvals unlock only after `finalize sprint`."
        ]
    }


def build_thread_actions(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return Slack/Telegram-friendly draft review and finalization actions."""
    sections = build_review_sections(summary)
    actions = [
        {
            "id": "help",
            "label": "Show Flywheel capabilities and commands",
            "thread_command": "help",
            "status": "available",
            "scope": "help",
            "aliases": ["what can you do?", "commands", "capabilities"],
            "safety_note": "Explains what Flywheel can do and how to interact with it."
        },
        {
            "id": "start-walkthrough",
            "label": "Walk me through the draft step by step",
            "thread_command": "start walkthrough",
            "status": "available",
            "scope": "guided_review",
            "safety_note": "Switches from dashboard review to sequential section review."
        },
        {
            "id": "finalize-sprint",
            "label": "Finalize sprint after section review",
            "thread_command": "finalize sprint",
            "status": "blocked_until_sections_reviewed",
            "scope": "plan_finalization",
            "safety_note": "Finalizes the sprint plan only; it does not send, post, or spend."
        },
        {
            "id": "revise",
            "label": "Ask Flywheel to revise the draft sprint",
            "thread_command": "revise <what to change>",
            "status": "available",
            "scope": "revision",
            "safety_note": "Use in Slack to steer the GTM employee in-thread."
        },
        {
            "id": "show-approvals",
            "label": "Show review/finalization status",
            "thread_command": "show approvals",
            "status": "available",
            "scope": "review_status",
            "safety_note": "Lists remaining draft sections before finalization."
        }
    ]
    for section in sections:
        actions.append({
            "id": f"review-{section['id']}",
            "label": f"Review {section['label']}",
            "thread_command": section["review_command"],
            "status": "draft",
            "scope": section["id"],
            "approve_command": section["approve_command"],
            "edit_command": section["edit_command"],
            "safety_note": "Approves or edits this plan section; execution approvals unlock only after `finalize sprint`."
        })
    return actions


def save_run_ledger(report: Dict[str, Any], args, output_path, run_id) -> str:
    """Save a lightweight run ledger for Slack/thread-native demos.

    run_id is shared with the sprint approval state so the ledger and the
    approval state machine refer to the same sprint.
    """
    summary = report["sprint_summary"]
    run_ledger = {
        "run_id": run_id,
        "source": "demo_or_slack",
        "status": "completed",
        "generated_at": report["generated_at"],
        "product": summary.get("product_name"),
        "thread_native_interface": {
            "primary_surface": "Slack or Telegram",
            "mention_pattern": "@Flywheel run a GTM sprint for <product> / send Flywheel a GTM sprint request",
            "quiet_callbacks": True,
            "human_thread_receives": ["ack", "help_message", "draft_review_dashboard", "optional_walkthrough", "finalization_commands"],
            "audit_only": ["script_progress", "intermediate_generation", "validation_details"]
        },
        "artifacts": [
            artifact_ref(output_path),
            artifact_ref(output_path.with_suffix(".md")),
            artifact_ref(out_path(args, "outbound_queue.md")),
            artifact_ref(out_path(args, "creator_campaign.md")),
            artifact_ref(out_path(args, "mpp_spend_cards.md")),
            artifact_ref(out_path(args, "mpp_spend_cards.json")),
            artifact_ref(out_path(args, "mpp_receipts.json")),
            artifact_ref(out_path(args, "trend_content.md"))
        ],
        "approval_actions": build_thread_actions(summary),
        "audit_notes": [
            "All outbound, posting, and spend actions remain approval-gated.",
            "Stripe MPP spend cards model paid GTM procurement and require founder approval before any payment authorization.",
            "Routine progress should stay out of the human Slack thread.",
            "The final callback should summarize outcomes and ask for numbered approvals."
        ]
    }
    write_json(out_path(args, f"runs/{run_id}.json"), run_ledger)
    latest_path = write_json(out_path(args, "runs/latest_run.json"), run_ledger)
    print(f"✓ Run ledger saved to {latest_path}")
    return str(latest_path)


def save_sprint_report(summary: Dict[str, Any], all_data: Dict[str, Any], next_week: Dict[str, Any],
                       args, run_id: str, learning: Dict[str, Any]):
    """Save complete sprint report to JSON."""
    output_path = out_path(args, "weekly_flywheel_sprint.json")

    report = {
        "generated_at": datetime.now().isoformat(),
        "run_id": run_id,
        "sprint_summary": summary,
        "learning": learning,
        "detailed_data": all_data,
        "next_week_plan": next_week,
        "help_catalog": build_help_catalog(),
        "thread_actions": build_thread_actions(summary),
        "review_sections": build_review_sections(summary),
        "draft_review_flow": {
            "default_mode": "dashboard",
            "walkthrough_command": "start walkthrough",
            "finalize_command": "finalize sprint",
            "execution_locked_until_finalized": True,
            "status": "draft_not_finalized"
        },
        "slack_callback_policy": {
            "quiet_by_default": True,
            "post_to_thread": ["ack", "help_message", "draft_review_dashboard", "optional_walkthrough", "finalization_commands"],
            "keep_audit_only": ["script_progress", "intermediate_generation", "validation_details"]
        },
        "report_version": "1.3"
    }

    write_json(output_path, report)

    print(f"✓ Sprint report saved to {output_path}")

    # Also save markdown report
    md_path = output_path.with_suffix('.md')
    save_sprint_markdown(report, md_path)
    save_run_ledger(report, args, output_path, run_id)

    return output_path

def save_sprint_markdown(report: Dict[str, Any], output_path):
    """Save human-readable sprint report markdown."""

    summary = report["sprint_summary"]
    next_week = report["next_week_plan"]
    learning = report.get("learning", {}) or {}

    md_content = f"""# Weekly Customer Acquisition Flywheel Sprint

**Product:** {summary['product_name']}
**Sprint Week:** {summary['sprint_week']}
**Generated:** {report['generated_at']}
**Demo Mode:** {summary.get('demo_mode', False)}

---

## 🎯 Executive Summary

**Total Actions Generated:** {summary['total_actions']}
**Content Pieces:** {summary['total_content_pieces']}
**Budget Utilization:** {summary['budget_analysis']['budget_utilization']}% (${summary['budget_analysis']['creator_spend_proposed']} of ${summary['budget_analysis']['weekly_budget']} weekly budget)

### Channel Breakdown
- 🚀 **Launch Channels:** {summary['channel_breakdown']['launch_channels']}
- 🔗 **Backlink Opportunities:** {summary['channel_breakdown']['backlink_opportunities']}
- 📧 **Warm Leads:** {summary['channel_breakdown']['warm_leads']}
- 🎬 **Creator Partnerships:** {summary['channel_breakdown']['creator_partnerships']}

### Estimated Impact (Illustrative)

_Illustrative planning estimates, not forecasts._

- **Weekly Traffic:** {summary['estimated_weekly_impact']['estimated_weekly_traffic']:,} visitors
- **Content Reach:** {summary['estimated_weekly_impact']['estimated_content_reach']:,} impressions
- **Creator Reach:** {summary['estimated_weekly_impact']['estimated_creator_reach']:,} followers
- **Outbound Responses:** {summary['estimated_weekly_impact']['estimated_outbound_responses']} expected

"""

    if learning.get("has_history"):
        last = learning.get("last_sprint") or {}
        md_content += f"""---

## 🔁 vs Last Sprint (Flywheel Learning)

Building on **{learning.get('prior_sprints', 0)}** prior sprint(s). Last sprint the founder approved **{last.get('approved', 0)}** item(s), rejected **{last.get('rejected', 0)}**, executed **{last.get('executed', 0)}**, and approved **${last.get('approved_spend_usd', 0)}** in spend.

**Channel priorities this week (by past approval rate):**
"""
        scores = learning.get("opportunity_scores", {})
        if scores:
            for sec, s in sorted(scores.items(), key=lambda kv: (kv[1].get("approval_rate") or 0), reverse=True):
                rate = s.get("approval_rate")
                rate_txt = f"{int(rate * 100)}%" if rate is not None else "n/a"
                md_content += f"- **{sec}**: {rate_txt} approved ({s.get('approved', 0)}/{s.get('decided', 0)} decided)\n"
        else:
            md_content += "- No decisions recorded yet — this sprint's approvals seed next week's priorities.\n"

    md_content += """---

## 🔥 Top 5 Priority Actions (This Week)

"""

    for i, action in enumerate(summary.get("top_5_actions", []), 1):
        effort_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(action.get("effort", "medium"), "🟡")
        md_content += f"""### {i}. {action['action']} {effort_emoji}

**Type:** {action['type'].title()} | **Priority Score:** {action['priority']}/100 | **Timeline:** {action['timeline']}

"""

    approval_gates = summary.get("approval_gates", {})

    md_content += f"""---

## 📝 Draft Review Dashboard (Default Slack Flow)

**Status:** Draft sprint — not finalized, not approved for execution.

Flywheel should show this dashboard first so the user can choose a section to inspect/edit. If the user wants a guided flow, they can switch to the walkthrough.

| Section | Status | Review | Approve/Edit |
|---|---|---|---|
"""

    for section in report.get("review_sections", build_review_sections(summary)):
        md_content += (
            f"| **{section['label']}** | {section['status']} | "
            f"`{section['review_command']}` | `{section['approve_command']}` / `{section['edit_command']}` |\n"
        )

    md_content += f"""

### Thread / Chat Commands

- `help` / `commands` / `what can you do?` — show Flywheel capabilities and command menu
- `review launch` / `review backlinks` / `review outbound` / `review content` / `review mpp spend` / `review budget` — inspect a section from the dashboard
- `approve <section>` — approve a plan section, not execution
- `edit <section>: <change>` — revise one section
- `start walkthrough` — switch to guided step-by-step review
- `finalize sprint` — lock the sprint after review; execution commands unlock only after this
- `show approvals` — list section review and finalization status

### Execution Approval Gates (Locked Until Finalized)

- 📧 **Outbound Messages:** {approval_gates.get('outbound_messages', 0)} require execution approval after finalization
- 💰 **Spend Requests:** {approval_gates.get('spend_requests', 0)} totaling ${approval_gates.get('total_spend_amount', 0)} require execution approval after finalization
- 💳 **Stripe MPP Spend Cards:** {approval_gates.get('mpp_spend_cards', 0)} totaling ${approval_gates.get('mpp_pending_amount', 0)} require founder approval before payment authorization
- 📱 **Content Posts:** {approval_gates.get('content_posts', 0)} social media posts require execution approval after finalization
- 🚦 **All external actions remain blocked until section review + `finalize sprint`**

Flywheel should keep routine progress quiet and return the acknowledgement, draft dashboard, optional walkthrough steps, and finalization commands to the human thread/chat.

---

## 📊 Detailed Sprint Breakdown

### 🚀 Launch Strategy
"""

    launch_data = report["detailed_data"].get("launch_plan", {})
    if launch_data.get("launch_channels"):
        md_content += f"""
**Channels Ready:** {len(launch_data['launch_channels'])}
**Asset Requirements:** {len(launch_data.get('asset_requirements', []))} items

**Top 3 Launch Priorities:**
"""
        for i, channel in enumerate(launch_data["launch_channels"][:3], 1):
            md_content += f"{i}. **{channel['name']}** (Score: {channel.get('priority_score', 0)}) - {channel.get('effort', 'medium')} effort\n"
    else:
        md_content += "\n*No launch plan generated - run launch_plan.py*\n"

    md_content += f"""
### 🔗 Backlink Opportunities
"""

    backlink_data = report["detailed_data"].get("backlink_opportunities", {})
    if backlink_data.get("opportunities"):
        md_content += f"""
**Opportunities Found:** {backlink_data.get('total_opportunities', 0)}
**High Impact:** {len([o for o in backlink_data['opportunities'] if o.get('estimated_impact') == 'high'])}
**Low Effort:** {len([o for o in backlink_data['opportunities'] if o.get('estimated_effort') == 'low'])}

**Top 3 Opportunities:**
"""
        for i, opp in enumerate(backlink_data["opportunities"][:3], 1):
            md_content += f"{i}. **{opp['title'][:60]}...** (Score: {opp.get('score', 0)}) - {opp.get('type', 'listing').replace('_', ' ').title()}\n"
    else:
        md_content += "\n*No backlink opportunities generated - run backlink_hunter.py*\n"

    md_content += f"""
### 📧 Warm Outbound Queue
"""

    leads_data = report["detailed_data"].get("outbound_queue", {})
    if leads_data.get("leads"):
        md_content += f"""
**Total Leads:** {leads_data.get('total_leads', 0)}
**High Priority:** {leads_data.get('high_priority', 0)} (ICP score 80+)
**Average Fit Score:** {leads_data.get('avg_score', 0):.1f}/100

**Priority Outreach:**
"""
        high_priority_leads = [l for l in leads_data["leads"] if l.get("priority") == "high"][:3]
        for i, lead in enumerate(high_priority_leads, 1):
            md_content += f"{i}. **{lead['name']}** at {lead['company']} (Score: {lead.get('icp_fit_score', 0)}) - {lead.get('title', 'Professional')}\n"
    else:
        md_content += "\n*No outbound queue generated - run lead_scorer.py*\n"

    md_content += f"""
### 🎬 Creator Campaigns
"""

    creator_data = report["detailed_data"].get("creator_campaign", {})
    if creator_data.get("campaign_proposals"):
        budget_status = "✅ Within Budget" if summary['budget_analysis']['within_budget'] else "⚠️ Exceeds Budget"
        md_content += f"""
**Campaign Proposals:** {creator_data.get('total_proposals', 0)}
**Total Budget:** ${creator_data.get('total_budget', 0)} | **Upfront:** ${summary['budget_analysis']['creator_spend_proposed']}
**Budget Status:** {budget_status}

**Top Creator Partnerships:**
"""
        for i, proposal in enumerate(creator_data["campaign_proposals"][:3], 1):
            md_content += f"{i}. **{proposal['creator']}** ({proposal['platform']}, {proposal['followers']:,} followers) - {proposal['campaign_name']}\n"
    else:
        md_content += "\n*No creator campaigns generated - run creator_campaign.py*\n"

    md_content += f"""
### 💳 Stripe MPP GTM Procurement
"""

    mpp_data = report["detailed_data"].get("mpp_spend_cards", {})
    receipt_data = report["detailed_data"].get("mpp_receipts", {})
    if mpp_data.get("spend_cards"):
        md_content += f"""
**MPP Spend Cards:** {mpp_data.get('total_spend_cards', 0)}
**Pending MPP Amount:** ${mpp_data.get('total_pending_amount_usd', 0)}
**Receipts After Approval:** {receipt_data.get('total_receipts', 0)} test receipts

Flywheel treats Stripe MPP as the transaction layer for approved GTM procurement: paid data, creator tests, launch placements, and execution infrastructure stay locked as spend cards until the founder approves.

| Card | Paid GTM Resource | Amount | Approval Command |
|---|---|---:|---|
"""
        for card in mpp_data["spend_cards"]:
            md_content += f"| `{card['id']}` | {card['resource_name']} | ${card['amount_usd']} | `{card['approval_command']}` |\n"
    else:
        md_content += "\n*No MPP spend cards generated - run mpp_spend_planner.py*\n"

    md_content += f"""
### 📈 Trend Content
"""

    content_data = report["detailed_data"].get("trend_content", {})
    if content_data.get("content_drafts"):
        total_reach = sum(d.get("estimated_reach", {}).get("organic_impressions", 0) for d in content_data["content_drafts"])
        md_content += f"""
**Content Pieces:** {content_data.get('total_content_pieces', 0)}
**Estimated Reach:** {total_reach:,} impressions
**Platforms:** Twitter, LinkedIn, Reddit, TikTok, YouTube

**Top Content Opportunities:**
"""
        for i, content in enumerate(content_data["content_drafts"][:3], 1):
            reach = content.get("estimated_reach", {}).get("organic_impressions", 0)
            md_content += f"{i}. **{content['platform']}** - {content['trend'][:50]}... ({reach:,} est. impressions)\n"
    else:
        md_content += "\n*No trend content generated - run trend_scan.py*\n"

    md_content += f"""
---

## 📅 Next Week Focus: {next_week['week']}

### 🎯 Primary Focus Areas
{chr(10).join(f"- {focus}" for focus in next_week.get('focus_areas', []))}

### ✅ Follow-Up Actions
{chr(10).join(f"- {action}" for action in next_week.get('follow_up_actions', []))}

### 🔧 Optimization Opportunities
{chr(10).join(f"- {opp}" for opp in next_week.get('optimization_opportunities', []))}

### 📚 Compound Learning
{chr(10).join(f"- {learning}" for learning in next_week.get('compound_learning', []))}

---

## 🚦 Sprint Execution Checklist

### Pre-Execution (Must Complete Before Actions)
- [ ] **Review all priority actions above**
- [ ] **Approve outbound messages** ({approval_gates.get('outbound_messages', 0)} waiting)
- [ ] **Approve spend requests** (${approval_gates.get('total_spend_amount', 0)} total)
- [ ] **Approve Stripe MPP spend cards** (${approval_gates.get('mpp_pending_amount', 0)} total, autonomous spend remains $0)
- [ ] **Approve content posts** ({approval_gates.get('content_posts', 0)} drafted)
- [ ] **Verify budget allocation** ({summary['budget_analysis']['budget_utilization']}% of weekly budget)

### Execution Phase
- [ ] Execute approved launch channel submissions
- [ ] Send approved outbound messages and backlink requests
- [ ] Publish approved social content according to calendar
- [ ] Execute approved creator partnership agreements
- [ ] Set up tracking for all activities

### Post-Execution
- [ ] Monitor performance metrics daily
- [ ] Respond to engagement within 24 hours
- [ ] Document what worked for next sprint
- [ ] Prepare learnings for next week's flywheel run

---

## ⚡ Key Reminders

1. **🚦 ALL external actions require explicit approval** - no auto-send, no auto-spend
2. **💳 Stripe MPP is approval-gated** - paid GTM resources become spend cards before payment authorization
3. **💰 Budget tracking** - weekly limit ${summary['budget_analysis']['weekly_budget']}, single spend max ${summary['budget_analysis'].get('max_single_spend_usd', 25)}
4. **📊 Performance tracking** - measure what works for compound learning
5. **🔄 Weekly cadence** - run this flywheel every Monday for consistent growth
6. **🎯 Focus on execution** - plans only work when actions are taken

**This sprint represents one week of focused customer acquisition work. Approve, execute, measure, learn, repeat.**
"""

    write_text(output_path, md_content)

    print(f"✓ Sprint markdown report saved to {output_path}")

def main():
    """Main sprint report generation workflow."""
    configure_stdout()
    print("📋 Flywheel Agent - Sprint Report Generator")
    print("Compiling weekly customer acquisition flywheel sprint...\n")

    parser = build_parser("Compile all GTM activities into the weekly flywheel sprint report.", research=False)
    parser.add_argument(
        "--new-sprint",
        action="store_true",
        help="Start a new sprint (archive the prior one to history) instead of "
             "continuing the current one. Re-compiling without this flag preserves "
             "founder approvals.",
    )
    args = parser.parse_args()

    try:
        # Load product profile
        profile = load_profile(args)
        print(f"✓ Loaded profile for {profile['product_name']}")

        # Load all generated data
        all_data = {
            "launch_plan": load_json_safely(out_path(args, "launch_plan.json")),
            "backlink_opportunities": load_json_safely(out_path(args, "backlink_opportunities.json")),
            "outbound_queue": load_json_safely(out_path(args, "outbound_queue.json")),
            "creator_campaign": load_json_safely(out_path(args, "creator_campaign.json")),
            "mpp_spend_cards": load_json_safely(out_path(args, "mpp_spend_cards.json")),
            "mpp_receipts": load_json_safely(out_path(args, "mpp_receipts.json")),
            "trend_content": load_json_safely(out_path(args, "trend_content.json"))
        }

        # Count loaded components
        loaded_components = len([k for k, v in all_data.items() if v is not None])
        print(f"✓ Loaded {loaded_components}/7 sprint components")

        # Partial pipelines are the normal state after any exit-2 stage:
        # normalize missing components to {} so the report degrades to a
        # partial report instead of crashing on None.
        all_data = {k: (v or {}) for k, v in all_data.items()}

        if loaded_components == 0:
            print("❌ No sprint components found. Run other scripts first:")
            print("   - flywheel_intake.py")
            print("   - launch_plan.py")
            print("   - backlink_hunter.py")
            print("   - lead_scorer.py")
            print("   - creator_campaign.py")
            print("   - trend_scan.py")
            return EXIT_ERROR

        # Generate executive summary
        summary = generate_executive_summary(profile, all_data)
        print("✓ Generated executive summary")

        # Seed the approval state machine for this sprint. This archives the
        # prior sprint's decisions to history (if the founder engaged with it),
        # so the learning loop below reflects what they actually approved.
        run_id = datetime.now().strftime("flywheel-%Y%m%d-%H%M%S-%f") + f"-{os.getpid()}"
        state_dir = ledger.state_dir_for(args)
        sprint_state = ledger.seed_sprint(
            state_dir, run_id, profile.get("product_name"), all_data,
            generated_at=summary.get("generated_at"), new_sprint=args.new_sprint)
        # A continued sprint keeps its original id; only a new sprint uses the
        # freshly minted one. Report and approval state must agree.
        run_id = sprint_state.get("run_id", run_id)
        if sprint_state.get("sprint_state") == ledger.SPRINT_FINALIZED and not args.new_sprint:
            print("ℹ️  Continuing a finalized sprint; approvals preserved. Use --new-sprint for a new week.")
        learning = ledger.learning_summary(ledger.read_history(state_dir))
        if learning.get("has_history"):
            print(f"✓ Learning loop: {learning['prior_sprints']} prior sprint(s) inform next week")

        # Generate next week plan (ordered by prior-sprint approvals)
        next_week = generate_next_week_plan(profile, all_data, learning)
        print("✓ Generated next week plan")

        # Save complete report
        output_path = save_sprint_report(summary, all_data, next_week, args, run_id, learning)

        # Print summary
        approval_gates = summary.get("approval_gates", {})

        print(f"\n📊 Weekly Sprint Summary:")
        print(f"   Product: {summary['product_name']}")
        print(f"   Total Actions: {summary['total_actions']}")
        print(f"   Content Pieces: {summary['total_content_pieces']}")
        print(f"   Budget Utilization: {summary['budget_analysis']['budget_utilization']}%")
        print(f"   Estimated Weekly Traffic: {summary['estimated_weekly_impact']['estimated_weekly_traffic']:,}")

        print(f"\n📝 Draft Review Required:")
        print(f"   Review Sections: launch, backlinks, outbound, content, mpp spend, budget")
        print(f"   Optional Walkthrough: start walkthrough")
        print(f"   Finalization Gate: finalize sprint")
        print(f"   Execution-locked Items: {approval_gates.get('outbound_messages', 0)} outbound, ${approval_gates.get('total_spend_amount', 0)} creator spend, ${approval_gates.get('mpp_pending_amount', 0)} MPP spend cards, {approval_gates.get('content_posts', 0)} content posts")

        if summary.get("demo_mode"):
            print("\n🎭 Running in DEMO MODE")

        print(f"\n✅ Draft sprint report complete! Review sections, edit if needed, then finalize the sprint before execution approvals.")
        print(f"📄 Full report: {output_path.with_suffix('.md')}")
        return EXIT_OK

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Unexpected error: {e}")
        return EXIT_ERROR

if __name__ == "__main__":
    import sys
    sys.exit(main())