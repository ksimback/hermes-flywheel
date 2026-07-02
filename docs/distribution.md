# Flywheel Agent Distribution Guide

Flywheel Agent is packaged as a Hermes Profile Distribution so users can install a complete GTM employee from GitHub instead of copying prompts, scripts, cron jobs, and configuration by hand.

## Install

### Existing Hermes install

```bash
hermes profile install github.com/ksimback/hermes-flywheel --alias --yes
hermes -p flywheel-agent setup --portal   # or: hermes -p flywheel-agent model
flywheel-agent chat
```

### Fresh machine or VPS

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc 2>/dev/null || true
hermes setup --portal
hermes profile install github.com/ksimback/hermes-flywheel --alias --yes
hermes -p flywheel-agent setup --portal   # profile config is isolated
flywheel-agent chat
```

> This repository is intended to be public. Install commands assume `github.com/ksimback/hermes-flywheel` is reachable; if you fork it privately, users need GitHub credentials with access to your fork.

For local testing before GitHub push:

```bash
hermes profile install . --name flywheel-agent-smoke --force -y
hermes profile info flywheel-agent-smoke
```

## Slack Teammate Mode

After configuring the Hermes Slack gateway, invite Flywheel to a channel and tag it as your GTM employee:

```text
@Flywheel run a GTM sprint for [product].
ICP: [buyer]
Competitors: [2-5 competitors]
Budget: [$ weekly budget]
Focus: [launch / outbound / creators / content]
```

Flywheel should acknowledge in-thread, keep routine progress quiet, and return a draft review dashboard by default. Users can ask `help`, `commands`, or `what can you do?` for a compact capabilities/menu message. They can inspect sections with `review launch`, `review backlinks`, `review outbound`, `review content`, `review mpp spend`, and `review budget`, or switch to sequential mode with `start walkthrough`. `finalize sprint` locks the plan; execution approvals and MPP payments remain unavailable before finalization. Full setup: [`docs/slack-gtm-employee.md`](slack-gtm-employee.md).

## Update

```bash
hermes profile update flywheel-agent
```

Distribution-owned files update cleanly. User-owned memories, sessions, chats, `.env`, API keys, auth tokens, and local tweaks stay local.

## Required/Optional Keys

No paid keys are required for the deterministic demo pipeline. Optional keys:

- `NVIDIA_API_KEY` — optional NVIDIA/NIM/Nemotron sponsor path.
- `OPENAI_API_KEY` — optional fallback model provider.
- `SLACK_BOT_TOKEN` — optional Slack bot token for the GTM employee demo.
- `SLACK_APP_TOKEN` — optional Slack app-level token for Socket Mode.
- `STRIPE_API_KEY` — optional Stripe MPP simulated test-mode transaction path for approval-gated GTM procurement.
- `STRIPE_WEBHOOK_SECRET` — optional Stripe webhook verification.
- `SERPER_API_KEY` — optional web-search API for headless research runs.

Copy `.env.EXAMPLE` to `.env` and fill keys locally. Never commit `.env`.

## Safety

Flywheel never sends outbound messages, posts to social platforms, or spends money without explicit approval. All generated outbound and spend items are marked for human approval.

## Distribution-Owned Files

- `distribution.yaml`
- `SOUL.md`
- `config.yaml`
- `mcp.json`
- `cron/`
- `skills/flywheel-agent/`
- `README.md`
- `docs/`
- `demo/`
- sample `data/`

## User-Owned Files Never Shipped

- `.env`
- `auth.json`
- `memories/`
- `sessions/`
- `state.db*`
- live API keys or payment credentials
