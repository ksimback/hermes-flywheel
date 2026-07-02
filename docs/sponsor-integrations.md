# Sponsor Integration Proof

> This material originated as a hackathon submission (hence the sponsor-by-sponsor framing below). The underlying pipeline is now a maintained standalone tool — the CLI works independently of any of this; this doc just documents how each sponsor technology maps onto the codebase.

**What is Hermes?** Hermes is a separate, external agent runtime built by Nous Research (hermes-agent.nousresearch.com). It is not part of this repository. You only need it for the chat/Slack/Telegram experience. The standalone CLI runs the full GTM pipeline without Hermes — see README "A. Standalone CLI".

Flywheel connects the three hackathon sponsor technologies into one product story: a GTM employee that plans, reasons, and transacts inside the founder's existing chat surface.

## Summary

| Sponsor | Flywheel role | Proof in repo |
|---|---|---|
| Hermes Agent by Nous Research | Runtime and chat-native employee layer | Hermes profile distribution, Slack/Telegram commands, draft dashboard, approval gates |
| NVIDIA Nemotron | GTM reasoning layer | Model-config knob at the Hermes-runtime layer only (see note below) |
| Stripe MPP | Transaction layer for paid GTM resources | MPP spend cards, simulated 402 challenges, test receipts, sprint ledger artifacts |

**NVIDIA/Nemotron note:** this is a Hermes-runtime model-config knob, not a code path in the Python pipeline. `config.yaml` ships with `model: ""` (intentionally unset — you choose the provider via `hermes -p flywheel-agent model`), and `distribution.yaml` just declares the `NVIDIA_API_KEY` env var as optional. There is no NVIDIA-specific code anywhere in the deterministic scripts; "proof in repo" for this row is config-level only.

## Stripe MPP: GTM procurement layer (real test mode + simulation fallback)

Stripe MPP is not treated as a generic payment logo. In Flywheel, MPP is the mechanism that turns a proposed paid GTM action into an approval-gated machine payment flow.

The honesty guarantee, in short:

- **No key, or no `sk_test_...` key:** the MPP flow is explicitly a simulation. No live Stripe API is called, and every generated spend card and receipt carries `"simulated": true`.
- **Genuine Stripe test key (`sk_test_...`) set:** `mpp_spend_planner.py` (via `skills/flywheel-agent/scripts/stripe_client.py`) creates real, unconfirmed test-mode `PaymentIntent`s for each spend card, so the founder sees genuine authorization objects in their own Stripe test dashboard instead of fabricated ids. Those intents have no payment method attached and `capture_method: manual`, so no charge is ever authorized or captured either way. The resulting receipt is marked `"simulated": false, "stripe_test_mode": true` (never a bare `"simulated": false`), so provenance stays honest even for a real object.
- **Live keys (`sk_live_...`):** refused outright by `stripe_client.get_test_key()`. This integration will never touch live money.
- **Any Stripe call errors:** that card falls back to a simulated receipt, so the pipeline never breaks.

**The `stripe-mcp-server` entry in `mcp.json` is NOT bundled with this repo.** It's a placeholder for a separate, optional future integration — the server binary doesn't exist here and isn't required. The built-in Stripe path (`stripe_client.py`, used by `mpp_spend_planner.py`) is plain stdlib HTTP calls to Stripe's REST API and needs no MCP server at all.

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
