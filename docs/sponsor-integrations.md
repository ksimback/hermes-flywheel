# Sponsor Integration Proof

Flywheel connects the three hackathon sponsor technologies into one product story: a GTM employee that plans, reasons, and transacts inside the founder's existing chat surface.

## Summary

| Sponsor | Flywheel role | Proof in repo |
|---|---|---|
| Hermes Agent by Nous Research | Runtime and chat-native employee layer | Hermes profile distribution, Slack/Telegram commands, draft dashboard, approval gates |
| NVIDIA Nemotron | GTM reasoning layer | Sprint planning language and NVIDIA API configuration path for model-backed reasoning |
| Stripe MPP | Transaction layer for paid GTM resources | MPP spend cards, simulated 402 challenges, test receipts, sprint ledger artifacts |

## Stripe MPP: GTM procurement layer (simulated test mode)

Stripe MPP is not treated as a generic payment logo. In Flywheel, MPP is the mechanism that turns a proposed paid GTM action into an approval-gated machine payment flow.

The current MPP flow is **explicitly a simulation**: no live Stripe API is called, and every generated spend card and receipt carries the `"simulated": true` field. Stripe MCP (the `stripe-mcp-server` entry in `mcp.json`) is an optional future integration; `mcp.json` is a placeholder config and the server binary is not bundled with this repo.

The intended loop is:

1. Flywheel identifies a paid GTM resource during a weekly sprint.
2. The provider responds with an MPP-style `402 Payment Required` challenge.
3. Flywheel converts the challenge into a Slack/Telegram approval card.
4. The founder approves or rejects the card.
5. After approval, Flywheel authorizes the payment in test mode.
6. The paid resource unlocks and a Stripe-style receipt is saved to the sprint ledger.

The deterministic demo creates four paid GTM resource cards:

- creator test
- competitor demand data pull
- launch placement
- browser execution session

Artifacts:

- `demo/demo-output/mpp_spend_cards.json`
- `demo/demo-output/mpp_receipts.json`
- `demo/demo-output/mpp_spend_cards.md`
- `demo/demo-output/weekly_flywheel_sprint.json`
- `demo/demo-output/runs/latest_run.json`

## Safety model

Flywheel keeps autonomous spend at `$0` in the demo. Every MPP card includes:

- `status: awaiting_founder_approval`
- `approval_command`
- `reject_command`
- `payment_challenge.http_status: 402`
- `payment_challenge.test_mode: true`
- `"simulated": true`
- `founder_guardrails.autonomous_spend_limit_usd: 0`

This makes MPP explicit without pretending live money moved during the demo.

## Run the proof

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

Expected result: validator prints `All validations passed` and the sprint report includes a Stripe MPP GTM Procurement section.
