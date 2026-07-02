"""Tests for skills/flywheel-agent/scripts/research.py.

research.py is the headless SERPER research path: it turns a live web search
into the --input JSON that backlink_hunter.py / trend_scan.py consume, for
cron/headless runs with no interactive agent attached.

Two test styles are used, matching repo convention:
  - Pure shaping functions (build_backlink_queries, build_opportunities,
    build_trend_queries, build_trends, _domain) are direct-imported and unit
    tested (see tests/test_units.py for the sys.path-insert pattern).
  - CLI behavior (exit codes, no-key handling, and feeding real backlink
    output into backlink_hunter.py) is tested via subprocess (see
    tests/test_completeness.py's run() helper).

Nothing here makes a real network call: serper_search() itself is never
invoked, and the no-key paths are exercised specifically so no network call
can happen.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "flywheel-agent" / "scripts"

sys.path.insert(0, str(SCRIPTS))

import research  # noqa: E402


# ---------------------------------------------------------------------------
# subprocess helper (mirrors tests/test_completeness.py's run())
# ---------------------------------------------------------------------------

def run(cmd, env=None, check=False):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=check,
    )


def _env_without_key():
    env = dict(os.environ)
    env.pop("SERPER_API_KEY", None)
    return env


def _env_with_placeholder_key():
    env = dict(os.environ)
    env["SERPER_API_KEY"] = "replace_with_serper_key"
    return env


# ---------------------------------------------------------------------------
# 1. No-key / placeholder-key path: exit 2, actionable message, no output file
# ---------------------------------------------------------------------------

class TestMissingKeyExitsCleanly:
    def test_no_key_exits_2_and_writes_nothing(self, tmp_path):
        out = tmp_path / "backlinks.json"
        result = run(
            [
                sys.executable, str(SCRIPTS / "research.py"),
                "--profile", "data/product_profile.json",
                "--for", "backlinks",
                "--output", str(out),
            ],
            env=_env_without_key(),
        )
        assert result.returncode == 2, result.stdout
        assert "SERPER_API_KEY" in result.stdout
        assert "--input" in result.stdout
        assert "--demo" in result.stdout
        assert not out.exists()

    def test_placeholder_key_exits_2_and_writes_nothing(self, tmp_path):
        out = tmp_path / "trends.json"
        result = run(
            [
                sys.executable, str(SCRIPTS / "research.py"),
                "--profile", "data/product_profile.json",
                "--for", "trends",
                "--output", str(out),
            ],
            env=_env_with_placeholder_key(),
        )
        assert result.returncode == 2, result.stdout
        assert "SERPER_API_KEY" in result.stdout
        assert "--input" in result.stdout
        assert "--demo" in result.stdout
        assert not out.exists()

    def test_no_key_message_mentions_target(self, tmp_path):
        out = tmp_path / "backlinks.json"
        result = run(
            [
                sys.executable, str(SCRIPTS / "research.py"),
                "--profile", "data/product_profile.json",
                "--for", "backlinks",
                "--output", str(out),
            ],
            env=_env_without_key(),
        )
        assert "backlinks" in result.stdout


# ---------------------------------------------------------------------------
# 2. _domain
# ---------------------------------------------------------------------------

class TestDomain:
    def test_strips_scheme_and_path_and_lowercases(self):
        assert research._domain("https://Dir.Example/x") == "dir.example"

    def test_http_scheme(self):
        assert research._domain("http://Example.com/a/b/c") == "example.com"

    def test_bare_domain_no_scheme(self):
        assert research._domain("example.com/path") == "example.com"

    def test_empty_or_none(self):
        assert research._domain("") == ""
        assert research._domain(None) == ""


# ---------------------------------------------------------------------------
# 3. build_backlink_queries
# ---------------------------------------------------------------------------

class TestBuildBacklinkQueries:
    def test_includes_category_directory_query(self):
        profile = {"category": "e-commerce intelligence", "competitors": []}
        queries = research.build_backlink_queries(profile)
        assert "e-commerce intelligence tools directory" in queries
        assert "best e-commerce intelligence tools" in queries

    def test_competitor_as_url_becomes_alternatives_query(self):
        profile = {"category": "software", "competitors": ["https://cartpilot.example"]}
        queries = research.build_backlink_queries(profile)
        assert "cartpilot alternatives" in queries

    def test_competitor_as_bare_name_becomes_alternatives_query(self):
        profile = {"category": "software", "competitors": ["ShopFlow"]}
        queries = research.build_backlink_queries(profile)
        assert "ShopFlow alternatives" in queries

    def test_limits_to_four_competitors(self):
        profile = {
            "category": "software",
            "competitors": ["a.example", "b.example", "c.example", "d.example", "e.example"],
        }
        queries = research.build_backlink_queries(profile)
        # 2 base queries + at most 4 competitor queries
        assert len(queries) <= 6

    def test_defaults_when_profile_sparse(self):
        queries = research.build_backlink_queries({})
        assert "software tools directory" in queries


# ---------------------------------------------------------------------------
# 4. build_opportunities
# ---------------------------------------------------------------------------

PROFILE = {
    "product_name": "RealCo",
    "url": "https://realco.example",
    "category": "dev tools",
    "one_liner": "Dev tools for founders",
    "icp": {"buyer": "dev tool founders"},
}

OPPORTUNITY_KEYS = {
    "id", "type", "source_url", "title", "description", "why_relevant",
    "estimated_effort", "estimated_impact", "recommended_action",
    "outreach_template",
}


class TestBuildOpportunities:
    def test_empty_input_returns_empty_list(self):
        assert research.build_opportunities({}, PROFILE) == []

    def test_dedups_by_domain(self):
        results_by_query = {
            "dev tools directory": [
                {"title": "Page A", "link": "https://acme.example/a", "snippet": "s1"},
                {"title": "Page B", "link": "https://acme.example/b", "snippet": "s2"},
            ],
        }
        opps = research.build_opportunities(results_by_query, PROFILE)
        assert len(opps) == 1
        assert opps[0]["source_url"] == "https://acme.example/a"

    def test_two_different_domains_produce_two_items(self):
        results_by_query = {
            "dev tools directory": [
                {"title": "Page A", "link": "https://acme.example/a", "snippet": "s1"},
                {"title": "Page B", "link": "https://beta.example/b", "snippet": "s2"},
            ],
        }
        opps = research.build_opportunities(results_by_query, PROFILE)
        assert len(opps) == 2

    def test_every_item_has_full_schema(self):
        results_by_query = {
            "q": [{"title": "T", "link": "https://acme.example/a", "snippet": "s"}],
        }
        opps = research.build_opportunities(results_by_query, PROFILE)
        assert len(opps) == 1
        assert set(opps[0].keys()) == OPPORTUNITY_KEYS

    def test_ids_are_sequential_opp_prefixed(self):
        results_by_query = {
            "q": [
                {"title": "T1", "link": "https://a.example/1", "snippet": "s"},
                {"title": "T2", "link": "https://b.example/2", "snippet": "s"},
                {"title": "T3", "link": "https://c.example/3", "snippet": "s"},
            ],
        }
        opps = research.build_opportunities(results_by_query, PROFILE)
        assert [o["id"] for o in opps] == ["opp_001", "opp_002", "opp_003"]

    def test_respects_limit(self):
        results_by_query = {
            "q": [
                {"title": f"T{i}", "link": f"https://site{i}.example/{i}", "snippet": "s"}
                for i in range(10)
            ],
        }
        opps = research.build_opportunities(results_by_query, PROFILE, limit=3)
        assert len(opps) == 3

    def test_skips_results_without_link(self):
        results_by_query = {
            "q": [{"title": "No link"}, {"title": "Has link", "link": "https://acme.example/a"}],
        }
        opps = research.build_opportunities(results_by_query, PROFILE)
        assert len(opps) == 1


# ---------------------------------------------------------------------------
# 5. build_trend_queries / build_trends
# ---------------------------------------------------------------------------

TREND_KEYS = {
    "trend", "platform", "volume", "relevance", "example_post",
    "viral_potential", "keywords",
}


class TestBuildTrendQueries:
    def test_includes_category_trend_and_news_queries(self):
        profile = {"category": "dev tools", "icp": {"keywords": []}}
        queries = research.build_trend_queries(profile)
        assert "dev tools trends" in queries
        assert "dev tools news" in queries

    def test_includes_keyword_queries(self):
        profile = {"category": "dev tools", "icp": {"keywords": ["ci/cd", "observability"]}}
        queries = research.build_trend_queries(profile)
        assert "ci/cd trend" in queries
        assert "observability trend" in queries

    def test_limits_to_three_keywords(self):
        profile = {"category": "dev tools", "icp": {"keywords": ["a", "b", "c", "d", "e"]}}
        queries = research.build_trend_queries(profile)
        # 2 base + at most 3 keyword queries
        assert len(queries) <= 5


class TestBuildTrends:
    def test_empty_input_returns_empty_list(self):
        assert research.build_trends({}, PROFILE) == []

    def test_every_item_has_full_schema(self):
        results_by_query = {
            "dev tools trends": [{"title": "New CI trend", "snippet": "s"}],
        }
        trends = research.build_trends(results_by_query, PROFILE)
        assert len(trends) == 1
        assert set(trends[0].keys()) == TREND_KEYS

    def test_dedups_by_title(self):
        results_by_query = {
            "q1": [{"title": "Same Title", "snippet": "s1"}],
            "q2": [{"title": "Same Title", "snippet": "s2"}],
        }
        trends = research.build_trends(results_by_query, PROFILE)
        assert len(trends) == 1

    def test_respects_limit(self):
        results_by_query = {
            "q": [{"title": f"Trend {i}", "snippet": "s"} for i in range(20)],
        }
        trends = research.build_trends(results_by_query, PROFILE, limit=4)
        assert len(trends) == 4

    def test_skips_results_without_title(self):
        results_by_query = {"q": [{"snippet": "no title here"}]}
        assert research.build_trends(results_by_query, PROFILE) == []


# ---------------------------------------------------------------------------
# 6. Integration: pure-function research output feeds backlink_hunter.py
# ---------------------------------------------------------------------------

def run_script(cmd, check=False):
    return subprocess.run(
        [sys.executable] + [str(c) for c in cmd],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


class TestResearchOutputFeedsBacklinkHunter:
    def test_research_shaped_input_flows_through_pipeline(self, tmp_path):
        # Build a real (non-demo) product profile.
        profile_path = tmp_path / "profile.json"
        result = run_script([
            SCRIPTS / "flywheel_intake.py",
            "Product: RealCo (https://realco.example) ICP: dev tool founders "
            "Competitors: acme.example, beta.example Budget: $200 "
            "Focus: launch Category: dev tools",
            "--output", profile_path,
        ])
        assert result.returncode == 0, result.stdout
        with profile_path.open(encoding="utf-8") as f:
            profile = json.load(f)
        assert profile["demo_mode"] is False

        # Shape fake (offline) Serper-style search results with the same pure
        # functions research.py uses, simulating what a real search would
        # produce -- no network call, no fixture leakage.
        results_by_query = {
            "dev tools tools directory": [
                {
                    "title": "Dev Tools Directory Listing",
                    "link": "https://devtoolsdirectory.test/listings/realco",
                    "snippet": "A directory of developer tools for founders.",
                },
            ],
        }
        opportunities = research.build_opportunities(results_by_query, profile)
        assert opportunities

        research_input = {
            "opportunities": opportunities,
            "source": "serper_live_search",
            "product_name": profile.get("product_name"),
        }
        research_input_path = tmp_path / "research_backlinks.json"
        research_input_path.write_text(
            json.dumps(research_input), encoding="utf-8"
        )

        out_dir = tmp_path / "out"
        result = run_script([
            SCRIPTS / "backlink_hunter.py",
            "--profile", profile_path,
            "--output-dir", out_dir,
            "--input", research_input_path,
        ])
        assert result.returncode == 0, result.stdout

        with (out_dir / "backlink_opportunities.json").open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["data_source"] == "agent_research"
        assert data["demo_mode"] is False
        assert "example.com" not in json.dumps(data)
        assert data["total_opportunities"] == len(opportunities)
