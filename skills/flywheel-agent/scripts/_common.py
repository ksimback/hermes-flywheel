#!/usr/bin/env python3
"""
Shared helpers for the Flywheel script pipeline.

These scripts are designed to be invoked as tools by the Hermes agent in
response to prompts and approvals received via Telegram or Slack. That
imposes a few hard requirements:

- Scripts can be launched from any working directory, so all relative
  paths are anchored to the repo root.
- stdout/stderr must never crash on Unicode (chat-friendly output includes
  emoji, and Windows consoles default to cp1252).
- Fixture/sample data is only used for explicit demos. For a real founder
  request, the agent performs research with its own toolsets (web, browser)
  and passes structured findings via --input. Missing research is a clear,
  actionable failure - never a silent fixture fallback.
- Exit codes are meaningful so the agent can react in-thread:
  0 = success, 1 = error, 2 = research input required.
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path


def _find_root():
    """Locate the repo root, tolerating a relocated scripts directory."""
    default = Path(__file__).resolve().parents[3]
    if (default / "skills" / "flywheel-agent").exists():
        return default
    for parent in Path(__file__).resolve().parents:
        if (parent / "distribution.yaml").exists() or (parent / "skills" / "flywheel-agent").exists():
            return parent
    return default


ROOT = _find_root()

DEFAULT_OUTPUT_DIR = "demo/demo-output"
DEFAULT_PROFILE_PATH = "data/product_profile.json"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MISSING_INPUT = 2


def configure_stdout():
    """Force UTF-8 text streams so emoji output never crashes on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def anchor(path):
    """Anchor a possibly-relative path to the repo root.

    Relative paths must resolve inside the repo root; absolute paths remain
    allowed as explicit intent (tests and CI write to temp directories).
    """
    path = Path(path)
    if path.is_absolute():
        return path
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        print(f"❌ {path} escapes the repo root; pass an absolute path to write elsewhere.")
        sys.exit(EXIT_ERROR)
    return resolved


def read_text(path):
    return anchor(path).read_text(encoding="utf-8")


def write_text(path, content):
    path = anchor(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(str(tmp_path), str(path))
    return path


def read_json(path):
    with anchor(path).open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = anchor(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(str(tmp_path), str(path))
    return path


def build_parser(description, research=True):
    """Standard CLI contract shared by all pipeline scripts.

    Scripts that consume agent research get --input/--demo; profile-derived
    scripts (launch_plan, mpp_spend_planner, sprint_report, validate_outputs)
    pass research=False so unsupported flags fail loudly instead of being
    silently ignored.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_PATH,
        help="Path to the product profile JSON created by flywheel_intake.py.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated artifacts (relative paths anchor to the repo root).",
    )
    if research:
        parser.add_argument(
            "--input",
            dest="input_path",
            help=(
                "Path to structured research JSON supplied by the agent "
                "(see SKILL.md for the per-script schema)."
            ),
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Explicitly allow bundled sample fixture data.",
        )
    return parser


def load_profile(args):
    """Load the product profile or exit with an agent-actionable message."""
    profile_path = anchor(args.profile)
    if not profile_path.exists():
        print(f"❌ Product profile not found: {profile_path}")
        print("   Run flywheel_intake.py first to create the product profile.")
        sys.exit(EXIT_ERROR)
    with profile_path.open(encoding="utf-8") as f:
        return json.load(f)


def out_path(args, filename):
    """Resolve an artifact path under the configured output directory."""
    return anchor(args.output_dir) / filename


def fixture_allowed(args, profile):
    """Fixture data is allowed only for explicit demos."""
    return bool(getattr(args, "demo", False) or profile.get("demo_mode"))


def exit_missing_input(what, schema_hint, extra_lines=None):
    """Exit with the standard agent-actionable missing-research message."""
    print(f"❌ No research input provided for {what}, and this is not a demo run.")
    print(f"   Supply agent research with: --input <path to JSON with '{what}'>")
    print(f"   Expected schema: {schema_hint}")
    for line in extra_lines or []:
        print(f"   {line}")
    print("   Or run the explicit demo fixture with --demo.")
    sys.exit(EXIT_MISSING_INPUT)


def resolve_research(args, profile, what, schema_hint, fixture=None):
    """Return (items, data_source) for a pipeline stage.

    Priority: agent-supplied --input JSON, then the bundled fixture if
    explicitly in demo mode. A real (non-demo) run without research input
    exits with EXIT_MISSING_INPUT so the calling agent can gather research
    and retry, or tell the founder what is missing.
    """
    if getattr(args, "input_path", None):
        data = read_json(args.input_path)
        items = data.get(what) if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            print(f"❌ --input file has no usable '{what}' entries: {args.input_path}")
            print(f"   Expected schema: {schema_hint}")
            sys.exit(EXIT_ERROR)
        for item in items:
            if not isinstance(item, dict):
                print(f"❌ --input '{what}' entries must be JSON objects, got {type(item).__name__}: {args.input_path}")
                print(f"   Expected schema: {schema_hint}")
                sys.exit(EXIT_ERROR)
        return items, "agent_research"
    if fixture_allowed(args, profile):
        return copy.deepcopy(fixture or []), "sample_fixture"
    exit_missing_input(what, schema_hint)


def artifact_demo_mode(profile, data_source):
    """Provenance rule: an artifact is demo-mode if its data came from the
    sample fixture or the profile itself is a demo profile."""
    return data_source == "sample_fixture" or bool(profile.get("demo_mode", False))


def artifact_is_stale(artifact, profile):
    """Provenance rule: why this artifact must NOT be consumed with this
    profile, or None if it may be.

    Stale = a demo-mode artifact being read by a real (non-demo) run, or an
    artifact stamped for a different product. Every artifact consumer
    (sprint_report, mpp_spend_planner, flywheel.py cleanup) must apply this,
    or leftovers from a prior --demo run get presented as real data.
    """
    if not isinstance(artifact, dict) or not artifact:
        return None
    if artifact.get("demo_mode") and not profile.get("demo_mode", False):
        return "demo-mode artifact left over from a --demo run"
    artifact_product = str(artifact.get("product_name") or "")
    product = str(profile.get("product_name") or "")
    if artifact_product and product and artifact_product != product:
        return f"stamped for '{artifact_product}', current product is '{product}'"
    return None


def get_proof_points(profile):
    """Sanitized positioning proof points for outbound/content copy.

    Never reads positioning.review_notes - those are internal disclaimers
    that must not reach founder-facing or outbound copy.
    """
    positioning = profile.get("positioning", {}) or {}
    return [str(p).strip() for p in (positioning.get("proof_points") or []) if str(p).strip()]


def get_pain_points(profile):
    """Sanitized ICP pain points for outbound/content copy."""
    icp = profile.get("icp", {}) or {}
    return [str(p).strip() for p in (icp.get("pain_points") or []) if str(p).strip()]


def md_safe(text):
    """Neutralize markdown structure in untrusted strings.

    Live web-search and agent-supplied text is embedded into the founder-facing
    sprint markdown, so defang the constructs that let such text escape its
    context or phish the reader: code-fence breakout, link syntax, and
    leading heading/blockquote markers.
    """
    s = str(text).replace("```", "ʼʼʼ")
    # Break clickable-link / image syntax so a search result can't inject a
    # disguised link into the founder's dashboard.
    s = s.replace("](", "] (")
    # Defang leading structural markers on any line (headings, blockquotes).
    out_lines = []
    for line in s.splitlines():
        stripped = line.lstrip()
        if stripped[:1] in ("#", ">"):
            line = line.replace(stripped[:1], "\\" + stripped[:1], 1)
        out_lines.append(line)
    return "\n".join(out_lines) if out_lines else s


def md_cell(text):
    """Escape untrusted strings for use inside a markdown table cell."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def safe_number(value, default):
    """Coerce a research-supplied value to float, degrading to default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
