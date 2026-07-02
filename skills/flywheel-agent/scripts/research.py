#!/usr/bin/env python3
"""
Headless research: turn live web search into the --input JSON that the
research-stage scripts consume, for cron/headless runs with no interactive
agent.

When SERPER_API_KEY is set, this makes a REAL Google search via Serper
(https://serper.dev) and shapes the organic results into a schema the
pipeline understands. With no key it exits with an actionable message and a
research-input-required code -- it never falls back to fixture data (that is
what `--demo` is for on the downstream scripts).

Scope, honestly: web search is a strong fit for backlink/listing discovery
and for trend signal, so those are what this produces. Warm outbound leads
need engagement data that a search API does not give, so leads stay on the
founder-CSV / interactive-agent path (see lead_scorer.py --leads-csv).

Usage:
    research.py --profile data/product_profile.json --for backlinks --output research/backlinks.json
    research.py --profile data/product_profile.json --for trends    --output research/trends.json

Then feed the result to the matching script:
    backlink_hunter.py --input research/backlinks.json
    trend_scan.py      --input research/trends.json

Exit codes: 0 success, 1 error, 2 research input required (no key / no query).
"""

import argparse
import json
import os
import socket
import sys
import traceback
import urllib.error
import urllib.request
from datetime import datetime

from _common import (
    EXIT_ERROR,
    EXIT_MISSING_INPUT,
    EXIT_OK,
    DEFAULT_PROFILE_PATH,
    anchor,
    configure_stdout,
    write_json,
)

SERPER_ENDPOINT = "https://google.serper.dev/search"


# ---------------------------------------------------------------------------
# Serper transport (the only part that touches the network)
# ---------------------------------------------------------------------------

def serper_search(query, api_key, num=10, timeout=15):
    """Run one Serper search. Returns the parsed JSON dict, or raises."""
    body = json.dumps({"q": query, "num": num}).encode("utf-8")
    req = urllib.request.Request(
        SERPER_ENDPOINT,
        data=body,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Pure shaping: search results -> pipeline --input schema (unit-tested offline)
# ---------------------------------------------------------------------------

def _domain(url):
    url = str(url or "")
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    return url.split("/")[0].lower()


def build_backlink_queries(profile):
    """Search intents that surface listing/directory/alternative pages."""
    category = profile.get("category") or "software"
    competitors = profile.get("competitors") or []
    queries = [f"{category} tools directory", f"best {category} tools"]
    for comp in competitors[:4]:
        name = _domain(comp) if str(comp).startswith("http") else str(comp)
        name = name.split(".")[0] if "." in name else name
        if name:
            queries.append(f"{name} alternatives")
    return queries


def build_opportunities(results_by_query, profile, limit=15):
    """Shape Serper organic results into backlink 'opportunities'.

    The result data (title, link, snippet) is real; the outreach copy is a
    conservative template the founder edits before anything is sent (every
    item stays approval-gated downstream).
    """
    product = profile.get("product_name") or "our product"
    url = profile.get("url") or ""
    one_liner = profile.get("one_liner") or f"{product} for {profile.get('category', 'growth')}"

    seen_domains = set()
    opportunities = []
    for query, results in results_by_query.items():
        for r in results:
            link = r.get("link") or r.get("url")
            if not link:
                continue
            dom = _domain(link)
            if not dom or dom in seen_domains:
                continue
            seen_domains.add(dom)
            title = r.get("title") or dom
            snippet = r.get("snippet") or ""
            opportunities.append({
                "id": f"opp_{len(opportunities) + 1:03d}",
                "type": "directory_listing",
                "source_url": link,
                "title": title,
                "description": snippet or f"Listing/resource surfaced for: {query}",
                "why_relevant": f"Ranks for '{query}', where {profile.get('icp', {}).get('buyer', 'the ICP')} look for tools like {product}.",
                "estimated_effort": "low",
                "estimated_impact": "medium",
                "recommended_action": f"Request {product} be added to this page/list.",
                "outreach_template": (
                    f"Hi,\n\nI came across your page \"{title}\". {product} ({url}) — {one_liner} — "
                    f"looks like a strong fit for it. Would you consider adding us? "
                    f"Happy to send any details you need.\n\nThanks!"
                ),
            })
            if len(opportunities) >= limit:
                return opportunities
    return opportunities


def build_trend_queries(profile):
    category = profile.get("category") or "software"
    keywords = (profile.get("icp") or {}).get("keywords") or []
    queries = [f"{category} trends", f"{category} news"]
    for kw in keywords[:3]:
        queries.append(f"{kw} trend")
    return queries


def build_trends(results_by_query, profile, limit=8):
    """Shape Serper organic results into 'trends' items."""
    keywords = (profile.get("icp") or {}).get("keywords") or []
    trends = []
    seen = set()
    for query, results in results_by_query.items():
        for r in results:
            title = r.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            trends.append({
                "trend": title,
                "platform": "web",
                "volume": "unknown",
                "relevance": query,
                "example_post": r.get("snippet") or "",
                "viral_potential": 50,
                "keywords": keywords[:5],
            })
            if len(trends) >= limit:
                return trends
    return trends


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

TARGETS = {
    "backlinks": ("opportunities", build_backlink_queries, build_opportunities),
    "trends": ("trends", build_trend_queries, build_trends),
}


def gather(target, profile, api_key):
    key_name, build_queries, shape = TARGETS[target]
    queries = build_queries(profile)
    results_by_query = {}
    for q in queries:
        try:
            data = serper_search(q, api_key)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                socket.timeout, OSError, ValueError) as exc:
            # socket.timeout is distinct from TimeoutError before Python 3.10;
            # a single failed query is skipped, not fatal to the whole run.
            print(f"⚠️  Search failed for '{q}': {exc}")
            continue
        # Guard shape: 'organic' may be absent, a non-list, or hold non-dict
        # items on a malformed response -- degrade instead of crashing.
        organic = data.get("organic") if isinstance(data, dict) else None
        results_by_query[q] = [r for r in organic if isinstance(r, dict)] if isinstance(organic, list) else []
    items = shape(results_by_query, profile)
    return key_name, items


def main():
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Produce --input research JSON from live web search (Serper)."
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE_PATH,
                        help="Product profile JSON from flywheel_intake.py.")
    parser.add_argument("--for", dest="target", required=True, choices=sorted(TARGETS),
                        help="Which research to produce.")
    parser.add_argument("--output", required=True,
                        help="Where to write the research JSON.")
    args = parser.parse_args()

    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if not api_key or api_key.startswith("replace_with"):
        print("❌ SERPER_API_KEY is not set, so live research is unavailable.")
        print(f"   Options: set SERPER_API_KEY for headless search, pass the {args.target} "
              f"research to the downstream script via --input, or use --demo for fixtures.")
        return EXIT_MISSING_INPUT

    try:
        profile_path = anchor(args.profile)
        if not profile_path.exists():
            print(f"❌ Product profile not found: {profile_path}")
            print("   Run flywheel_intake.py first.")
            return EXIT_ERROR
        with profile_path.open(encoding="utf-8") as f:
            profile = json.load(f)

        key_name, items = gather(args.target, profile, api_key)
        if not items:
            print(f"❌ No {args.target} results from search. Nothing written.")
            return EXIT_ERROR

        payload = {
            key_name: items,
            "source": "serper_live_search",
            "generated_at": datetime.now().isoformat(),
            "product_name": profile.get("product_name"),
        }
        out = write_json(args.output, payload)
        print(f"✓ Wrote {len(items)} {args.target} item(s) to {out}")
        print(f"   Feed it to the pipeline: --input {args.output}")
        return EXIT_OK
    except Exception as exc:
        traceback.print_exc()
        print(f"❌ Research error: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
