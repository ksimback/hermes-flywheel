# Stripe MPP Spend Cards

Generated: 2026-07-05T15:15:16.464643
Protocol: Stripe MPP
Demo mode: True

> **Simulated test-mode artifacts — no live Stripe call, no money moved.**

Flywheel uses Stripe MPP as the transaction layer for approved GTM procurement. Paid resources become approval cards, payment stays locked until the founder approves, and simulated test receipts return to the sprint ledger.

## MPP Workflow

- Flywheel discovers a paid GTM resource.
- The provider returns an MPP-style 402 payment challenge.
- Flywheel turns it into a founder approval card in Slack or Telegram.
- After approval, Flywheel pays programmatically in test mode and unlocks the resource.
- The Stripe receipt returns to the sprint ledger.

## Pending MPP Spend Cards

| Card | Resource | Amount | Approval command | Expected outcome |
|---|---|---:|---|---|
| `mpp_creator_001` | StoreGrowthDemo launch-week test | $100 | `approve mpp_creator_001` | 5-10 minute video review, written post/thread, demo walkthrough |
| `mpp_data_001` | Competitor demand data pull | $12 | `approve mpp_data_001` | paid competitor placement paths, source URLs, and outreach priority scores |
| `mpp_launch_001` | BetaList paid placement | $49 | `approve mpp_launch_001` | launch placement slot, submission receipt, and tracking link |
| `mpp_execution_001` | Browser execution session | $1 | `approve mpp_execution_001` | one browser automation session with receipt attached to the sprint ledger |

## Test Receipts After Approval

| Receipt | Card | PaymentIntent | Resource unlocked |
|---|---|---|---|
| `mpp_receipt_001` | `mpp_creator_001` | `pi_test_mpp_000001` | https://mpp.example.ai/resources/creator-test |
| `mpp_receipt_002` | `mpp_data_001` | `pi_test_mpp_000002` | https://mpp.example.ai/resources/competitor-demand-report |
| `mpp_receipt_003` | `mpp_launch_001` | `pi_test_mpp_000003` | https://mpp.example.ai/resources/launch-placement |
| `mpp_receipt_004` | `mpp_execution_001` | `pi_test_mpp_000004` | https://mpp.example.ai/resources/browser-session |

Simulated test-mode artifacts — no live Stripe call, no money moved.
