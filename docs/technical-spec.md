# Flywheel Agent Technical Spec

## Product

Flywheel Agent is a Hermes-powered GTM employee for early-stage founders. It turns a product profile, ICP, competitors, and budget into a weekly customer acquisition sprint.

## Runtime

- Hermes Profile Distribution
- Python 3.8+ deterministic scripts
- No paid keys required for demo mode
- Optional NVIDIA/NIM/Nemotron model path
- Optional Stripe MPP test-mode transaction path

## Core Data Flow

1. `flywheel_intake.py` creates `data/product_profile.json` from founder-provided context. The ExampleAI fixture is used only with `--demo`.
2. `launch_plan.py` creates launch plan JSON/Markdown.
3. `backlink_hunter.py` creates backlink/listing opportunities.
4. `lead_scorer.py` creates approval-gated outbound queue.
5. `creator_campaign.py` creates creator plan and creator spend requests.
6. `mpp_spend_planner.py` converts paid GTM resources into Stripe MPP spend cards, simulated 402 challenges, and test receipts.
7. `trend_scan.py` creates trend-based content drafts.
8. `sprint_report.py` aggregates all outputs into `weekly_flywheel_sprint.md` and writes Slack/thread actions.
9. `sprint_report.py` writes a lightweight run ledger to `demo/demo-output/runs/latest_run.json`.
10. `validate_outputs.py` checks completeness, safety gates, MPP guardrails, and receipt coverage.

## Outputs

All outputs are written under `demo/demo-output/`:

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

## Safety Invariants

- No real payment execution.
- No auto-DM, auto-email, or auto-post.
- All outbound drafts require human approval.
- All creator spend requests require human approval.
- All Stripe MPP payment authorizations require founder approval and run in deterministic test mode.
- Demo can run without secrets.
