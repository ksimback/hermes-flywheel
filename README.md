# Flywheel Agent

> **An installable Hermes Agent profile that acts like a GTM employee for early-stage founders.**

Flywheel turns a product, ICP, competitors, and budget into a weekly customer acquisition sprint. The agent researches launch channels, competitor demand paths, leads, creators, and trends using its own Hermes web/browser toolsets, then feeds those findings into the bundled scripts — a deterministic sprint pipeline that handles scoring, formatting, approval gates, and the run ledger. The result is a reviewable sprint with explicit approval gates before anything is sent, posted, or paid. Sample fixtures power the no-keys demo only.

Official website: **[hermesflywheel.com](https://hermesflywheel.com)**

## What is included

```text
SOUL.md                                  # Flywheel agent identity and operating rules
config.yaml                              # Safe Hermes profile defaults
distribution.yaml                        # Hermes profile distribution metadata
mcp.json                                 # MCP config placeholder
cron/weekly-gtm-sprint.json              # Optional recurring sprint job
skills/flywheel-agent/SKILL.md           # Main Flywheel skill
skills/flywheel-agent/scripts/           # Deterministic GTM sprint pipeline
skills/flywheel-agent/templates/         # Safe ExampleAI demo templates
demo/demo-output/                        # ExampleAI demo outputs for review/testing
docs/                                    # Install, architecture, sponsor integration, testing docs
tests/                                   # Public package completeness and pipeline tests
```

## Quick install

### If Hermes Agent is already installed

```bash
hermes profile install github.com/ksimback/hermes-flywheel --alias --yes
hermes -p flywheel-agent setup --portal
flywheel-agent chat
```

Then start with:

```text
start my acquisition flywheel
```

### Fresh machine

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc 2>/dev/null || true
hermes setup --portal
hermes profile install github.com/ksimback/hermes-flywheel --alias --yes
hermes -p flywheel-agent setup --portal
flywheel-agent chat
```

Hermes profiles are isolated. Even if your default Hermes profile already has a model configured, the Flywheel profile may still need its own provider/model selection with `hermes -p flywheel-agent setup --portal` or `hermes -p flywheel-agent model`.

## Usage

Flywheel can run in the terminal, Slack, or Telegram through Hermes Gateway.

Example prompt:

```text
Run a GTM sprint for ExampleAI.
ICP: e-commerce founders.
Competitors: CartPilot, ShopFlow, GrowthDock.
Budget: $2k this week.
Focus: warm outbound + creator distribution.
```

Flywheel replies with a short acknowledgement, works quietly, then returns a **draft review dashboard**. The default flow is:

```text
draft sprint -> review/edit sections -> optional walkthrough -> finalize sprint -> approve execution items
```

Useful commands inside the chat:

```text
help
commands
review launch
review backlinks
review outbound
review content
review mpp spend
start walkthrough
edit <section>: <change>
approve <section>
finalize sprint
show approvals
```

## Core loops

1. **Launch planning** - choose launch surfaces, write channel-specific angles, and queue launch tasks.
2. **Competitor demand** - find where adjacent products are listed, mentioned, or discussed.
3. **Warm outbound** - score leads and draft personalized messages for approval.
4. **Creator campaigns** - create creator briefs and test plans.
5. **Trend content** - turn current market conversations into demo-led narratives.
6. **Stripe MPP spend cards** - convert paid GTM resources into approval-gated payment cards.
7. **Weekly learning loop** - archive each sprint's approvals so next week's focus is ordered by the channels the founder actually greenlit.

## Approval workflow

The chat control phrases are backed by a persisted approval state machine (`approvals.py`), so approvals are real, durable state transitions — not prompt-only concepts. The flow is:

```text
draft dashboard -> review/edit -> finalize sprint -> approve <section>/<id> -> execute
```

- `finalize sprint` moves the sprint `draft -> finalized` and unlocks execution.
- `approve <section>` / `approve <id>` marks items approved; `execute` marks approved items sent/posted/paid.
- `show approvals` renders the current state.

The safety model is enforced in code, not just prose: nothing can be approved or executed while the sprint is a draft, and only approved items can be executed. `validate_outputs.py` fails if these invariants are violated. Approval state lives in `data/sprint_state.json` and archived history in `data/sprint_history.jsonl` — both founder-local and gitignored.

**Weekly learning loop:** when the next sprint is compiled, the prior sprint's approvals are archived, and Flywheel orders next week's focus by which sections the founder approved before — more of what gets greenlit, less of what gets rejected.

## Safety model

Flywheel is intentionally approval-gated:

- No auto-DMs.
- No auto-email.
- No auto-posting.
- No autonomous spend.
- Stripe MPP cards are simulated test-mode artifacts (`"simulated": true`) — no live Stripe calls.
- External actions require explicit founder approval.
- Demo fixture data is only used when `--demo` is passed.

## Stripe MPP GTM procurement

Flywheel treats Stripe MPP as the transaction layer for paid customer acquisition inputs.

The MPP artifacts are **simulated test-mode artifacts**: no live Stripe API call is made, and every generated card and receipt carries `"simulated": true`. Real Stripe MCP integration is on the roadmap.

The deterministic demo flow is:

1. Identify organic and paid GTM opportunities.
2. Convert paid resources into MPP-style spend cards.
3. Keep autonomous spend at `$0` until a founder approves.
4. Simulate the `402 Payment Required` challenge and test-mode authorization.
5. Save simulated receipts back to the sprint ledger.

Example spend card:

```json
{
  "id": "mpp_creator_001",
  "protocol": "stripe_mpp",
  "resource_type": "creator_test",
  "amount_usd": 75,
  "status": "awaiting_founder_approval",
  "approval_command": "approve mpp_creator_001",
  "payment_challenge": { "http_status": 402, "method": "stripe.mpp.charge" },
  "founder_guardrails": { "autonomous_spend_limit_usd": 0 }
}
```

See:

- [`docs/sponsor-integrations.md`](docs/sponsor-integrations.md)
- [`demo/demo-output/mpp_spend_cards.json`](demo/demo-output/mpp_spend_cards.json)
- [`demo/demo-output/mpp_receipts.json`](demo/demo-output/mpp_receipts.json)

## Demo run, no keys required

The ExampleAI fixture is public-safe and only used with `--demo`:

```bash
python skills/flywheel-agent/scripts/flywheel_intake.py --demo
python skills/flywheel-agent/scripts/launch_plan.py
python skills/flywheel-agent/scripts/backlink_hunter.py
python skills/flywheel-agent/scripts/lead_scorer.py
python skills/flywheel-agent/scripts/creator_campaign.py
python skills/flywheel-agent/scripts/mpp_spend_planner.py
python skills/flywheel-agent/scripts/trend_scan.py
python skills/flywheel-agent/scripts/sprint_report.py
python skills/flywheel-agent/scripts/validate_outputs.py
```

Result:

```text
demo/demo-output/weekly_flywheel_sprint.md
```

After a sprint is compiled, drive the approval state machine (still no keys required):

```bash
python skills/flywheel-agent/scripts/approvals.py finalize        # draft -> finalized, unlocks execution
python skills/flywheel-agent/scripts/approvals.py approve launch  # approve a section (or an item id)
python skills/flywheel-agent/scripts/approvals.py status          # show current approval state
```

Every script supports `--profile` and `--output-dir`; the research-stage scripts (`backlink_hunter`, `lead_scorer`, `creator_campaign`, `trend_scan`) also accept `--input` and `--demo`. Scripts work from any directory (paths anchor to the repo root). Windows is now supported alongside Linux and macOS.

In live (non-demo) runs, the research-stage scripts (`backlink_hunter`, `lead_scorer`, `creator_campaign`, `trend_scan`) expect agent-supplied research JSON via `--input` and exit with code 2 if it is missing — fixture data is only used with an explicit `--demo`.

## Optional environment variables

Copy `.env.EXAMPLE` to `.env` only for local/private use. Do not commit `.env`.

```bash
OPENAI_API_KEY=replace_with_openai_key
NVIDIA_API_KEY=replace_with_nvidia_key
SERPER_API_KEY=replace_with_serper_key
STRIPE_API_KEY=replace_with_stripe_test_key
STRIPE_WEBHOOK_SECRET=replace_with_stripe_webhook_secret
SLACK_BOT_TOKEN=replace_with_slack_bot_token
SLACK_APP_TOKEN=replace_with_slack_app_token
```

All keys are optional for the deterministic demo pipeline. These keys are currently consumed by the Hermes runtime/gateway (model providers, Slack, optional web search), not by the bundled scripts themselves.

## Slack and Telegram

Flywheel is chat-native when used with Hermes Gateway.

- Slack setup/testing: [`docs/slack-gtm-employee.md`](docs/slack-gtm-employee.md)
- Distribution setup: [`docs/distribution.md`](docs/distribution.md)

Telegram uses the same text-command flow as Slack: short acknowledgement, quiet work, draft dashboard, walkthrough, finalization, and separate execution approvals.

## Development

Install test dependencies with `pip install -e .[dev]` (or just `pip install pytest`), then run the full public package test suite:

```bash
python -m pytest -q
```

CI runs the suite on a Linux/macOS/Windows matrix (`.github/workflows/ci.yml`).

Run the deterministic validator only:

```bash
python skills/flywheel-agent/scripts/validate_outputs.py
```

## Public release hygiene

Before making a fork or mirror public:

```bash
git status --short
python -m pytest -q
git diff --check
```

This repo should not contain personal projects, private bot handles, access forms, landing-page assets, local caches, `.env` files, or unreviewed draft submission materials.

## License

MIT
