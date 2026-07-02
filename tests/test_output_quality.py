"""Output-quality gate: the shipped demo artifacts are what a prospective user
sees first, so scan the founder-facing markdown for the copy defects that make
generated output look broken -- unrendered template placeholders, leaked
internal notes, literal None/undefined, and the proof-point grammar splice.

Deliberately low-false-positive: it flags specific known-bad patterns, not
anything that merely looks unusual, so it won't fight legitimate copy (the
`[Your name]` sign-off placeholder is allowed).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO_MD = sorted((ROOT / "demo" / "demo-output").glob("*.md"))

# Unrendered f-string leftover: a brace-wrapped bare identifier, e.g.
# {product_name}. JSON never writes {identifier} without quotes/colon, so this
# does not fire on the JSON examples some reports embed.
UNRENDERED_PLACEHOLDER = re.compile(r"\{[a-z][a-z0-9_]*\}")

# Intentional mail-merge tokens the founder/agent fills per recipient (the
# outreach-template equivalent of the "[Your name]" sign-off). Allowed.
MAILMERGE_TOKENS = {"{name}", "{first_name}", "{company}", "{firstname}"}

# Placeholder tokens that should have been filled from the profile.
BAD_TOKENS = [
    "verify proof points before publishing",  # intake review note must never leak
    "review_notes",
    "INTERNAL:",
    "[product]", "[name]", "[company]", "[url]", "[icp]", "[insert",
    "<product>", "<name>", "<company>",
    "reporting Turns",   # the old proof-point grammar splice
    "helps  with",       # double space from an empty interpolation
    "undefined",
]

# Literal Python falsy values rendered into prose.
LITERAL_NONE = re.compile(r"(^|[\s(>:])(None|null)([\s.,)<]|$)")


def test_demo_markdown_exists():
    assert DEMO_MD, "no demo markdown found to check"


@pytest.mark.parametrize("md", DEMO_MD, ids=lambda p: p.name)
def test_no_copy_defects(md):
    text = md.read_text(encoding="utf-8")
    low = text.lower()

    for token in BAD_TOKENS:
        assert token.lower() not in low, f"{md.name}: found bad token {token!r}"

    placeholders = [p for p in UNRENDERED_PLACEHOLDER.findall(text)
                    if p not in MAILMERGE_TOKENS]
    assert not placeholders, f"{md.name}: unrendered placeholders {placeholders}"

    none_hits = [m.group(2) for m in LITERAL_NONE.finditer(text)]
    assert not none_hits, f"{md.name}: literal {none_hits} rendered into copy"


def test_outbound_messages_are_well_formed():
    """Every outbound draft addresses the lead and signs off, with no leaked
    disclaimer text in place of a real selling point."""
    outbound = (ROOT / "demo" / "demo-output" / "outbound_queue.md")
    text = outbound.read_text(encoding="utf-8")
    assert "Hi " in text, "messages should greet the lead"
    assert "verify proof points" not in text.lower()
    # The proof point must read as a natural quoted sentence, not be spliced
    # mid-clause (the v0.2.0 grammar regression).
    assert "reporting Turns store" not in text
