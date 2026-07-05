# Flywheel Agent

> **An installable Hermes Agent profile that acts like a GTM employee for early-stage founders.**

Flywheel turns a product, ICP, competitors, and budget into a weekly customer acquisition sprint: launch channels, competitor demand paths, warm outbound, creator campaigns, trend content, and approval-gated spend cards. Research comes from live sources (the Hermes chat agent's web/browser tools, a Serper search key, or your own leads CSV), then the bundled scripts handle scoring, formatting, approval gates, and the run ledger. The result is a reviewable sprint with explicit approval gates before anything is sent, posted, or paid. It runs two ways — a standalone CLI that needs only Python, or a full chat agent via Hermes — and the sample fixtures power a no-keys demo so you can see it work before configuring anything.

Official website: **[hermesflywheel.com](https://hermesflywheel.com)**

## Two ways to run Flywheel

Pick the path that fits you — they use the same pipeline underneath.

| | **A. Standalone CLI** | **B. Chat agent (Hermes)** |
|---|---|---|
| **What it is** | Run the Python pipeline directly | The full conversational GTM employee in terminal / Slack / Telegram |
| **Needs** | Python 3.8+ and git. Nothing else to try the demo. | [Hermes](#what-is-hermes) (an external runtime) plus a model provider |
| **Best for** | Trying it now, cron/automation, wiring Flywheel into your own agent | The "hire a GTM teammate" experience with live research and chat approvals |
| **Start here** | [Get the code](#get-the-code) → [Run a real sprint for your company](#run-a-real-sprint-for-your-company) | [Install as a Hermes profile](#b-chat-agent-via-hermes) |

Everything except the interactive chat surface runs standalone with no keys, so you can evaluate Flywheel end to end before deciding on Hermes.

## Prerequisites

- **Python 3.8+** and **git** (that's all you need for the CLI and the demo).
- Optional keys that unlock more of a *real* sprint (none required for the demo):
  - `SERPER_API_KEY` — live backlink/listing and trend research ([serper.dev](https://serper.dev)).
  - `STRIPE_API_KEY` (a **test** key, `sk_test_...`) — real test-mode payment authorization cards.
  - A leads CSV — your own warm-outbound targets.
  - Hermes + a model provider — only for the chat/Slack/Telegram experience.

## Get the code

```bash
git clone https://github.com/ksimback/hermes-flywheel
cd hermes-flywheel
python skills/flywheel-agent/scripts/flywheel.py doctor
```

`doctor` confirms your Python version, that the pipeline scripts are present, and which optional keys are configured. If it prints `✓ Ready.`, you can run the demo immediately (see [Verify your install](#verify-your-install)).

Shell snippets in this README are written for bash; they work as-is in Git Bash on Windows, and PowerShell equivalents are noted inline where they differ. If you prefer an isolated environment, create one first with `python -m venv .venv` and activate it.

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

## A. Standalone CLI (start here)

No Hermes, no keys — see a full sprint in one command:

```bash
python skills/flywheel-agent/scripts/flywheel.py run --demo
```

This wraps the whole deterministic pipeline (intake → launch → backlinks → leads → creators → MPP → trends → sprint report → validate) and writes a complete ExampleAI sprint to `demo/demo-output/weekly_flywheel_sprint.md`. To run it for *your* company, see [Run a real sprint for your company](#run-a-real-sprint-for-your-company) below.

## Run a real sprint for your company

Standalone, no Hermes. The pipeline always produces launch planning and approval-gated MPP cards from your product profile alone; each optional input below adds another live section. Anything you don't supply is skipped cleanly (a partial sprint you can fill in and re-run) — Flywheel never fabricates data for a real run.

```bash
# 1. (optional) Live backlink + trend research
export SERPER_API_KEY=sk_your_serper_key            # from serper.dev; unlocks backlinks + trends
#   PowerShell: $env:SERPER_API_KEY = "sk_your_serper_key"

# 2. (optional) Your warm-outbound targets
#    columns: name,title,company,bio,source,url,engagement_context
cp data/leads.example.csv data/leads.csv            # then edit with your real leads
#   PowerShell: Copy-Item data/leads.example.csv data/leads.csv

# 3. Compile the sprint from your product context
python skills/flywheel-agent/scripts/flywheel.py run \
  "Product: MyCo (https://myco.com) ICP: <who you sell to> Competitors: rival-a.com, rival-b.com Budget: $500 Focus: outbound + launch" \
  --leads-csv data/leads.csv

# 4. Review, then approve what you want to act on (nothing is sent/posted/paid automatically)
python skills/flywheel-agent/scripts/approvals.py status
python skills/flywheel-agent/scripts/approvals.py finalize
python skills/flywheel-agent/scripts/approvals.py approve outbound
```

What each input unlocks in a real (non-demo) run:

| Section | Requires | Without it |
|---|---|---|
| Launch plan | your product profile (always) | always included |
| MPP spend cards | your product profile (always) | always included (simulated unless a Stripe test key is set) |
| Backlinks & Trends | `SERPER_API_KEY` (or your own `--input` JSON) | skipped |
| Warm outbound | `--leads-csv <file>` or `data/leads.csv` | skipped |
| Creator campaigns | agent research via `--input` (no headless source yet) | skipped |

Read the result in `demo/demo-output/weekly_flywheel_sprint.md` (or the folder you pass to `--output-dir`). Re-running for the same product continues the sprint and preserves your approvals; pass `--new-sprint` to start a fresh week.

## B. Chat agent (via Hermes)

For the conversational GTM-employee experience (terminal, Slack, or Telegram), install Flywheel as a Hermes profile.

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

The Hermes installer targets Linux/macOS (on Windows, use WSL — or stay on the [standalone CLI](#a-standalone-cli-start-here), which is fully Windows-native):

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc 2>/dev/null || true
hermes setup --portal
hermes profile install github.com/ksimback/hermes-flywheel --alias --yes
hermes -p flywheel-agent setup --portal
flywheel-agent chat
```

Hermes profiles are isolated. Even if your default Hermes profile already has a model configured, the Flywheel profile may still need its own provider/model selection with `hermes -p flywheel-agent setup --portal` or `hermes -p flywheel-agent model`.

### What is Hermes?

Hermes is a separate open agent runtime from Nous Research — it provides the chat interface, model connection, web/browser research tools, and the Slack/Telegram gateway that turn these scripts into a conversational GTM teammate. **It is not part of this repository**, and you only need it for chat mode (paths above). The standalone CLI and the entire demo work without it. If the Hermes installer or your model provider isn't set up, use the [standalone CLI](#a-standalone-cli-start-here) instead — you get the same sprint, driven by commands rather than chat.

## Usage (chat mode)

In **chat mode** (path B, via Hermes) Flywheel runs in the terminal, Slack, or Telegram through Hermes Gateway. (Standalone CLI users drive the same flow with `flywheel.py run` and `approvals.py` — see [Run a real sprint for your company](#run-a-real-sprint-for-your-company).)

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

### Real Stripe test mode

If you set `STRIPE_API_KEY` to a genuine Stripe **test** key (`sk_test_...`), `mpp_spend_planner.py` creates real, unconfirmed test-mode `PaymentIntent`s instead of simulating them — so you can see the actual authorization objects in your Stripe test dashboard. Nothing is ever charged: intents are created without a payment method and with `capture_method: manual`, so they stay "authorization pending founder approval." Live keys (`sk_live_...`) are always refused outright — Flywheel never touches live money. With no key configured (the default), everything stays a labeled simulation (`"simulated": true`), exactly as described above.

## The pipeline stage by stage (under the hood)

`flywheel.py run --demo` runs all of the below for you. This is the granular view — useful for understanding each stage, running one in isolation, or wiring individual scripts into your own agent. The ExampleAI fixture is public-safe and only used with `--demo`:

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

For headless/cron runs with no interactive agent attached, `skills/flywheel-agent/scripts/research.py` can pre-generate that `--input` JSON for `backlink_hunter` and `trend_scan` by running a real search via Serper when `SERPER_API_KEY` is set:

```bash
python skills/flywheel-agent/scripts/research.py --profile data/product_profile.json --for backlinks --output research/backlinks.json
python skills/flywheel-agent/scripts/backlink_hunter.py --input research/backlinks.json
```

Without `SERPER_API_KEY` it exits cleanly with code 2 and actionable guidance — it never falls back to fixture data. Leads stay on the founder-CSV / interactive-agent path (`lead_scorer.py --leads-csv`); a search API cannot supply the engagement data leads need.

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

All keys are optional for the deterministic demo pipeline. Most are consumed by the Hermes runtime/gateway (model providers, Slack); `SERPER_API_KEY` is also read directly by `research.py` for headless search.

## Slack and Telegram

Flywheel is chat-native when used with Hermes Gateway.

- Slack setup/testing: [`docs/slack-gtm-employee.md`](docs/slack-gtm-employee.md)
- Distribution setup: [`docs/distribution.md`](docs/distribution.md)

Telegram uses the same text-command flow as Slack: short acknowledgement, quiet work, draft dashboard, walkthrough, finalization, and separate execution approvals.

## Verify your install

Three commands confirm a fresh clone works end to end, no keys required:

```bash
python skills/flywheel-agent/scripts/flywheel.py doctor   # environment/readiness
python skills/flywheel-agent/scripts/flywheel.py run --demo  # full ExampleAI sprint
python -m pytest -q                                        # full test suite
```

`doctor` should report Python OK and all scripts present; the demo run should end with `✓ Sprint compiled to demo/demo-output/weekly_flywheel_sprint.md`; the suite should pass. If all three succeed, the pipeline is working on your machine.

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
