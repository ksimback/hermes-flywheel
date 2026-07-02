# Flywheel Agent Technical Spec

## Product

Flywheel Agent is a Hermes-powered GTM employee for early-stage founders. It turns a product profile, ICP, competitors, and budget into a weekly customer acquisition sprint.

## Runtime

- Hermes Profile Distribution
- Python 3.8+ deterministic scripts (Linux, macOS, and Windows; CI runs a 3-OS matrix via `.github/workflows/ci.yml`)
- No paid keys required for demo mode
- Optional NVIDIA/NIM/Nemotron model path
- Optional Stripe MPP simulated test-mode transaction path

## Core Data Flow

The Hermes agent performs live research with its own web/browser toolsets, normalizes findings to per-script JSON schemas, and passes them to the deterministic pipeline via `--input`. The scripts handle scoring, formatting, approval gating, and the ledger.

CLI contract shared by all pipeline scripts:

- `--profile <path>` (default `data/product_profile.json`), `--output-dir <path>` (default `demo/demo-output`), `--input <path>` (agent-supplied research JSON), `--demo` (explicitly allow bundled sample fixtures).
- All paths anchor to the repo root, so scripts work from any working directory.
- Exit codes: `0` success, `1` error, `2` research input required — a live (non-demo) run of `backlink_hunter.py`, `lead_scorer.py`, `creator_campaign.py`, or `trend_scan.py` without `--input` exits 2 with an actionable message.

Pipeline stages:

1. `flywheel_intake.py` creates `data/product_profile.json` from founder-provided chat context. Marketing-safe `proof_points` stay empty for real founders until research validates them; internal `review_notes` are stored separately. The ExampleAI fixture is used only with `--demo`.
   - `research.py` (optional, headless research producer) — for cron/unattended runs with no interactive agent, `research.py --profile <path> --for backlinks|trends --output <path>` performs a real Serper search and shapes the results into the `--input` JSON that `backlink_hunter.py`/`trend_scan.py` expect. It consumes `SERPER_API_KEY`; without a real key (unset, or a placeholder starting with `replace_with`) it degrades to exit code `2` with actionable guidance and writes nothing — it never falls back to fixture data. Leads stay on the founder-CSV/interactive-agent path since search cannot supply engagement data.
2. `launch_plan.py` creates launch plan JSON/Markdown.
3. `backlink_hunter.py` scores agent-supplied backlink/listing research (`--input {"opportunities": [...]}`).
4. `lead_scorer.py` scores agent-supplied leads (`--input {"leads": [...]}` or `--leads-csv`) into an approval-gated outbound queue.
5. `creator_campaign.py` turns agent-supplied creator research (`--input {"creators": [...]}`) into a creator plan and spend requests.
6. `mpp_spend_planner.py` converts paid GTM resources into simulated Stripe MPP spend cards, simulated 402 challenges, and test receipts — every artifact is labeled `"simulated": true`; no live Stripe calls.
7. `trend_scan.py` turns agent-supplied trend research (`--input {"trends": [...]}`) into content drafts.
8. `sprint_report.py` aggregates all outputs into `weekly_flywheel_sprint.md` and writes Slack/thread actions. It also seeds the sprint's approval item registry, archives the prior (engaged) sprint to `data/sprint_history.jsonl`, and runs the learning loop (see below): the report JSON gains `run_id` and a `learning` block, and `next_week_plan` gains `based_on` and `vs_last_sprint`.
9. `sprint_report.py` writes a lightweight run ledger to `demo/demo-output/runs/latest_run.json` (or the configured `--output-dir`).
10. `validate_outputs.py` checks completeness, safety gates, MPP guardrails, receipt coverage, and the approval-state invariant (no approved/executed items in a draft sprint; only approved items executed).

Approval / learning components (shared state, not per-stage):

- `sprint_ledger.py` — the shared state and history model. Defines the item registry, load/save of `sprint_state.json`, the append-only `sprint_history.jsonl` writer/reader, the state transitions with their safety guards, and the learning-loop scoring (`opportunity_scores`, `learning_summary`). Imported by `sprint_report.py`, `approvals.py`, and `validate_outputs.py`.
- `approvals.py` — the approval state machine as an agent CLI. Subcommands `status | finalize | approve <id|section|all> | reject <target> | execute <id|approved>`, each taking `--profile <path>`. It maps the founder's chat commands (`show approvals`, `finalize sprint`, `approve <section>`, per-item approve/execute) onto durable transitions. Exit codes: `0` success, `1` blocked/error (the agent relays the message to the thread).

Entrypoint and transaction-layer components:

- `flywheel.py` — the one-command entrypoint. `flywheel.py run [--demo | context] [--profile] [--output-dir] [--new-sprint]` orchestrates stages 1-10 above as subprocesses; a real (non-demo) run skips any research-backed stage whose input isn't available (no `SERPER_API_KEY`, no `--input`, no `data/leads.csv`), producing a partial sprint instead of failing outright, and prints which stages were skipped and why. `flywheel.py doctor` checks the Python version, confirms all pipeline scripts are present, and reports `SERPER_API_KEY`/`STRIPE_API_KEY` readiness (including refusing to treat a non-test Stripe key as usable).
- `stripe_client.py` — a minimal stdlib-only Stripe test-mode client used by `mpp_spend_planner.py`. `get_test_key()`/`available()` gate on a genuine `sk_test_...` key (unset, placeholder, and `sk_live_...` keys all resolve to "unavailable"); `create_authorization_intent()` creates an unconfirmed, uncaptured test-mode `PaymentIntent` (no charge) or returns `{"error": ...}` without making a network call for invalid input.

### Approval state files (founder-local, gitignored)

Two durable files live beside the product profile (`data/`), never committed:

- `data/sprint_state.json` — the current sprint's approval state machine.
- `data/sprint_history.jsonl` — append-only, one summarized record per completed sprint.

### State machine

- Sprint level: `draft → finalized`. `finalize sprint` is the only transition; it unlocks execution approvals.
- Item level: `pending → approved | rejected`, and `approved → executed`. Approvable sections are `launch`, `backlinks`, `outbound`, `content`, `creator`, `mpp_spend`.
- Enforced invariant: while the sprint is a draft, nothing can be approved or executed; only `approved` items can be executed (marked sent/posted/paid). `validate_outputs.py` fails if this is violated, so the safety model is code, not prose.

### Learning loop

When a new sprint is compiled, the prior engaged sprint is archived to `sprint_history.jsonl`. `sprint_report.py` reads that history and computes a per-section approval rate (`opportunity_scores`), then orders next week's focus by what the founder actually approved — prioritizing high-approval sections and deprioritizing rejected ones. Once history exists, the markdown report shows a "vs Last Sprint (Flywheel Learning)" section.

## Outputs

All outputs are written under `demo/demo-output/` by default (configurable per run with `--output-dir`):

- `launch_plan.{json,md}`
- `backlink_opportunities.{json,md}`
- `outbound_queue.{json,md}`
- `creator_campaign.{json,md}`
- `mpp_spend_cards.{json,md}`
- `mpp_receipts.json`
- `trend_content.{json,md}`
- `weekly_flywheel_sprint.{json,md}`
- `runs/latest_run.json` plus timestamped run ledger entries

## Slack / Thread-Native Interface

Flywheel can run through the Hermes Slack gateway as a tagged GTM teammate. The interface contract is:

```text
@Flywheel mention -> short ack -> quiet generation -> draft dashboard -> optional walkthrough -> finalization -> execution/payment approvals
```

Routine progress should be audit-only. The human thread should receive the acknowledgement, draft review dashboard, optional walkthrough steps, finalization command, and approval cards.

## Stripe MPP Procurement Model

Stripe MPP acts as the transaction layer for paid GTM resources. The deterministic demo models:

- paid data access
- launch placement
- creator test
- browser execution infrastructure

Every MPP card includes a test-mode `402 Payment Required` challenge, founder approval command, reject command, `$0` autonomous spend limit, and matching test receipt.

**Real vs. simulated MPP receipts:** spend cards are always authorization challenges (`"simulated": true` in `mpp_spend_cards.json`, regardless of Stripe availability — no charge is ever represented as authorized). Receipts differ: with no Stripe test key configured, `mpp_receipts.json` sets `"simulated": true`; with a valid `sk_test_...` key, `mpp_spend_planner.py` calls `stripe_client.create_authorization_intent()` for each card and, on success, the receipt records `"simulated": false` alongside `"stripe_test_mode": true` and the real (unconfirmed, uncaptured) `PaymentIntent` id/dashboard URL. Any Stripe error falls back to a simulated receipt for that card so the pipeline never breaks. `validate_outputs.check_simulated_marker()` enforces the honesty invariant on every MPP artifact: `simulated: true` is honest, `simulated: false` paired with `stripe_test_mode: true` is honest (an explicit real test-mode artifact), but `simulated: false` without `stripe_test_mode` is a hard validation failure — it would otherwise imply an unlabeled live charge. A missing `simulated` field (old-format artifact) is warn-only.

## Safety Invariants

- No real payment execution.
- No auto-DM, auto-email, or auto-post.
- All outbound drafts require human approval.
- All creator spend requests require human approval.
- All Stripe MPP payment authorizations require founder approval and are deterministic simulations (`"simulated": true`) — no live Stripe calls.
- Demo can run without secrets.
