"""Unit tests for the deterministic logic inside the pipeline scripts."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "flywheel-agent" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import flywheel_intake  # noqa: E402
import _common  # noqa: E402


class TestValueForLabel:
    def test_extracts_labeled_field(self):
        raw = "Product: ExampleAI ICP: e-commerce founders Budget: $50"
        assert flywheel_intake._value_for_label(raw, ["icp"]) == "e-commerce founders"

    def test_returns_none_when_absent(self):
        assert flywheel_intake._value_for_label("no labels here", ["icp"]) is None


class TestSplitList:
    def test_splits_on_commas(self):
        assert flywheel_intake._split_list("A, B; C") == ["A", "B", "C"]

    def test_empty_input(self):
        assert flywheel_intake._split_list(None) == []
        assert flywheel_intake._split_list("") == []


class TestExtractUrl:
    def test_full_url(self):
        assert flywheel_intake._extract_url("see https://example.ai for details") == "https://example.ai"

    def test_bare_domain_gets_scheme(self):
        assert flywheel_intake._extract_url("Product: realco.example is neat") == "https://realco.example"

    def test_no_url(self):
        assert flywheel_intake._extract_url("no links at all") == ""


class TestExtractBudget:
    def test_plain_dollar_amount(self):
        budget = flywheel_intake._extract_budget("Budget: $250 weekly")
        assert budget["weekly_usd"] == 250

    def test_k_suffix(self):
        # The README's own example prompt uses "Budget: $2k this week".
        budget = flywheel_intake._extract_budget("Budget: $2k this week")
        assert budget["weekly_usd"] == 2000

    def test_comma_separated(self):
        budget = flywheel_intake._extract_budget("Budget: $1,500")
        assert budget["weekly_usd"] == 1500

    def test_default_when_missing(self):
        budget = flywheel_intake._extract_budget("no budget mentioned")
        assert budget["weekly_usd"] == 100
        assert budget["requires_approval"] is True

    def test_max_single_spend_bounds(self):
        assert 10 <= flywheel_intake._extract_budget("Budget: $20")["max_single_spend_usd"] <= 100
        assert flywheel_intake._extract_budget("Budget: $10,000")["max_single_spend_usd"] <= 100


class TestExtractProductName:
    def test_labeled_product(self):
        raw = "Product: ExampleAI (https://example.ai) ICP: founders"
        assert flywheel_intake._extract_product_name(raw) == "ExampleAI"

    def test_for_pattern(self):
        assert flywheel_intake._extract_product_name("Run a GTM sprint for RealCo today") == "RealCo"

    def test_multi_word_labeled_product_strips_parens(self):
        raw = "Product: My Cool Tool (https://x.example)"
        assert flywheel_intake._extract_product_name(raw) == "My Cool Tool"


class TestExtractBudgetSuffixes:
    def test_million_suffix(self):
        assert flywheel_intake._extract_budget("Budget: $1.5m")["weekly_usd"] == 1_500_000

    def test_decimal_k_suffix(self):
        assert flywheel_intake._extract_budget("Budget: $2.5k")["weekly_usd"] == 2500

    def test_zero_budget_extracts_zero_and_is_rejected(self):
        budget = flywheel_intake._extract_budget("Budget: $0")
        assert budget["weekly_usd"] == 0
        # validate_profile must reject a non-positive weekly budget.
        profile = flywheel_intake.normalize_input(
            "Product: RealCo (https://realco.example) Budget: $0"
        )
        assert profile["budget"]["weekly_usd"] == 0
        errors = flywheel_intake.validate_profile(profile)
        assert any("greater than $0" in e for e in errors)


class TestExtractUrlHardening:
    def test_budget_amount_is_not_a_url(self):
        assert flywheel_intake._extract_url("Budget: $1.5k weekly") == ""

    def test_version_string_is_not_a_url(self):
        assert flywheel_intake._extract_url("launching v2.0") == ""

    def test_bare_domain_promoted_to_https(self):
        assert flywheel_intake._extract_url("realco.example") == "https://realco.example"


class TestSanitizedCopyHelpers:
    """get_proof_points/get_pain_points must never leak internal review_notes."""

    def test_proof_points_empty_and_review_notes_never_leak(self):
        profile = {
            "positioning": {
                "proof_points": [],
                "review_notes": ["INTERNAL: verify claims before publishing"],
            }
        }
        result = _common.get_proof_points(profile)
        assert result == []
        assert "INTERNAL" not in str(result)

    def test_pain_points_read_from_icp_only(self):
        profile = {
            "icp": {"pain_points": ["manual work"]},
            "positioning": {"proof_points": [], "review_notes": ["INTERNAL note"]},
        }
        assert _common.get_pain_points(profile) == ["manual work"]
        assert "INTERNAL" not in str(_common.get_pain_points(profile))


class TestNormalizeInput:
    def test_empty_raises(self):
        with pytest.raises(ValueError):
            flywheel_intake.normalize_input("   ")

    def test_full_context(self):
        profile = flywheel_intake.normalize_input(
            "Product: RealCo (https://realco.example) ICP: dev tool founders "
            "Competitors: acme.example, beta.example Budget: $100 Focus: launch"
        )
        assert profile["product_name"] == "RealCo"
        assert profile["url"] == "https://realco.example"
        assert profile["demo_mode"] is False
        assert len(profile["competitors"]) == 2
        assert profile["budget"]["weekly_usd"] == 100
        # Marketing-safe proof points stay empty until validated by research;
        # internal guidance lives in review_notes.
        assert profile["positioning"]["proof_points"] == []
        assert profile["positioning"]["review_notes"]

    def test_demo_profile_is_labeled(self):
        profile = flywheel_intake.create_demo_profile()
        assert profile["demo_mode"] is True
        assert profile["budget"]["requires_approval"] is True
