# Flywheel Agent Complete Testing Plan

This plan verifies Flywheel Agent as a public Hermes profile distribution.

## Scope

The test suite must prove that the repository is ready for Founder to run locally and is safe to push as a private Hermes Profile Distribution.

## Test Gates

### Gate 1 — Distribution package completeness

Checks:
- `distribution.yaml` exists and declares `flywheel-agent`.
- `SOUL.md`, `config.yaml`, `mcp.json`, `.env.EXAMPLE`, `README.md`, and `cron/weekly-gtm-sprint.json` exist.
- `skills/flywheel-agent/SKILL.md` exists.
- All required scripts exist under `skills/flywheel-agent/scripts/`.
- Docs and demo files exist.

### Gate 2 — Secret and state safety

Checks:
- No `.env`, `auth.json`, state DB, sessions, memories, or live credential files are present.
- Markdown and JSON outputs do not contain obvious live credential patterns.
- `.gitignore` excludes user-owned state and secrets.

### Gate 3 — Python validity

Checks:
- All scripts compile with `python -m compileall`.
- Each script can run from the repo root with no paid keys when the explicit demo fixture is selected.
- `flywheel_intake.py` refuses no-argument live runs so fixture data cannot silently leak into user sprints.

### Gate 4 — Pipeline behavior

Checks:
- Full deterministic demo pipeline runs:
  1. `flywheel_intake.py --demo`
  2. `launch_plan.py`
  3. `backlink_hunter.py`
  4. `lead_scorer.py`
  5. `creator_campaign.py`
  6. `mpp_spend_planner.py`
  7. `trend_scan.py`
  8. `sprint_report.py`
  9. `validate_outputs.py`
- Generated outputs include product profile, launch plan, backlink opportunities, outbound queue, creator campaign, Stripe MPP spend cards/receipts, trend content, and weekly sprint report.

### Gate 5 — Plan acceptance criteria

Checks:
- Weekly sprint report exists and includes launch actions, opportunities, outbound drafts, creator campaign, MPP spend cards, test receipts, trend content, and next-week plan.
- Outbound items are approval-gated.
- MPP payment cards are approval-gated, test/demo-mode safe, and keep autonomous spend at `$0`.
- Installation/update instructions are present in README.
- NVIDIA/Nemotron integration path is documented as optional.

### Gate 6 — Local Hermes Profile Distribution install

Checks:
- `hermes profile install . --name flywheel-agent-smoke --force -y` succeeds from the repository root.
- `hermes profile info flywheel-agent-smoke` succeeds.
- Test profile is removed after smoke verification.

## Commands

```bash
cd <repo-root>
python -m compileall -q skills/flywheel-agent/scripts
python -m pytest -q
python skills/flywheel-agent/scripts/mpp_spend_planner.py
python skills/flywheel-agent/scripts/validate_outputs.py
hermes profile install . --name flywheel-agent-smoke --force -y
hermes profile info flywheel-agent-smoke
hermes profile delete flywheel-agent-smoke -y
```

## Pass Criteria

All gates pass with no critical or important findings. If Hermes profile smoke install cannot run due to local environment/version issues, document the exact blocker and keep the repo otherwise runnable.
