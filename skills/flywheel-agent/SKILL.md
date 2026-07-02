---
name: flywheel-agent
description: Run a weekly customer acquisition flywheel sprint for founders.
version: 0.3.0
platforms: [linux, macos, windows]
tags: [gtm, growth, stripe, nvidia, hermes, startup]
---

# Flywheel Agent

Use when the user asks to:
- start my acquisition flywheel
- run a GTM sprint
- find first customers
- launch-max this product
- find creator/paid distribution opportunities
- run weekly customer acquisition

## Safety Rules (Non-Negotiable)

1. **Never send outbound messages without explicit user approval**
2. **Never spend money without explicit user approval**
3. **Never scrape behind login walls or bypass platform limits**
4. **Treat all spend as pending until approved**
5. **Keep secrets out of markdown and logs**
6. **Mark all external actions as "requires_human_approval: true"**

## Required Inputs

Ask for missing fields only if they cannot be inferred:
- Product URL or description
- ICP (Ideal Customer Profile)
- 2–5 competitors
- Weekly budget ($25-500)
- Max single spend ($10-100)

## Core Procedure

You (the agent) do the research; the scripts do the deterministic work (scoring, formatting, approval gates, ledger). Run the scripts as tools from **any directory** — all paths anchor to the repo root, so there is no need to `cd` anywhere. Do **not** use `--demo` for a real user request.

### CLI contract (all pipeline scripts)

Every script accepts:

- `--profile <path>` — product profile JSON (default `data/product_profile.json`)
- `--output-dir <path>` — where artifacts go (default `demo/demo-output`)
- `--input <path>` — structured research JSON that you supply (see schemas below)
- `--demo` — explicitly allow the bundled ExampleAI sample fixtures (explicit demos only)

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error |
| 2 | Research input required — a live run of `backlink_hunter.py`, `lead_scorer.py`, `creator_campaign.py`, or `trend_scan.py` was invoked without `--input`. Provide `--input <research.json>`, or pass `--demo` only if the user explicitly asked for a demo. |

### `--input` schemas (JSON object with one key holding a list)

| Script | Schema |
|---|---|
| `backlink_hunter.py` | `{"opportunities": [{id, type, source_url, title, description, why_relevant, estimated_effort, estimated_impact, recommended_action, outreach_template}]}` |
| `lead_scorer.py` | `{"leads": [{name, title, company, bio, source, url, engagement_context}]}` (also accepts `--leads-csv` / `data/leads.csv`) |
| `creator_campaign.py` | `{"creators": [...]}` — same keys as the script's `SAMPLE_CREATORS` entries |
| `trend_scan.py` | `{"trends": [...]}` — same keys as the script's `SAMPLE_TRENDS` entries |

### 1. Intake & Profile Creation

Intake comes from founder-provided chat context (product, ICP, competitors, budget, focus):

```bash
python skills/flywheel-agent/scripts/flywheel_intake.py "Product: [name] ([url]) ICP: [buyer] Competitors: [2-5 names] Budget: [$ weekly] Focus: [priority]"
```

Creates or updates `data/product_profile.json` with normalized product context. Marketing-safe `proof_points` stay empty for real founders until research validates them; internal `review_notes` are kept separate. For explicit demos only: `python skills/flywheel-agent/scripts/flywheel_intake.py --demo`.

### 2. Launch Strategy Generation
```bash
python skills/flywheel-agent/scripts/launch_plan.py
```
Generates launch-max plan for Product Hunt, HN, directories, communities.

### 3. Backlink & Listing Discovery

Research where competitors are listed/mentioned using your own web/browser toolsets, normalize the findings to the `opportunities` schema, then:

```bash
python skills/flywheel-agent/scripts/backlink_hunter.py --input /path/to/backlink_research.json
```

Scores and formats the opportunities you found. Without `--input` (and without `--demo`) it exits 2 with an actionable message.

### 4. Lead Scoring & Warm Outbound

Gather real leads (engagement, signups, community activity), normalize to the `leads` schema, then:

```bash
python skills/flywheel-agent/scripts/lead_scorer.py --input /path/to/leads.json
```

Scores leads and drafts personalized approval-gated messages. Also accepts `--leads-csv` or `data/leads.csv`.

### 5. Creator Campaign Planning

Research niche creators relevant to the ICP, normalize to the `creators` schema, then:

```bash
python skills/flywheel-agent/scripts/creator_campaign.py --input /path/to/creators.json
```

Plans influencer partnerships with performance incentives and spend requests.

### 6. Trend Analysis & Content

Scan current trends with your web toolset, normalize to the `trends` schema, then:

```bash
python skills/flywheel-agent/scripts/trend_scan.py --input /path/to/trends.json
```

Generates trend-based content and weekly social media drafts.

### 7. Sprint Report Compilation
```bash
python skills/flywheel-agent/scripts/sprint_report.py
```
Compiles everything into `demo/demo-output/weekly_flywheel_sprint.md` (or the configured `--output-dir`).

## Slack / Telegram / Thread-Native Mode

When the sprint is triggered from Slack or Telegram:

- Acknowledge in the source thread/chat.
- Keep routine progress quiet unless there is a blocker.
- Never expose internal implementation notes (step-by-step narration of reading scripts, checking files, running intake) in the user-facing reply — that belongs in the audit trail. This is about noise, not provenance: always be honest about where data came from.
- For live product prompts, use the founder-provided product, ICP, competitors, budget, and focus as the product context, plus research you actually performed. Never present sample data as real research. If required research cannot be performed, say so plainly and ask for the inputs you need.
- Return a **draft review dashboard** by default, not a final/execution-ready sprint.
- Offer `start walkthrough` when the user wants a sequential section-by-section review.
- Use `review launch`, `review backlinks`, `review outbound`, `review content`, `review mpp spend`, `review budget`, `approve <section>`, `edit <section>: <change>`, `finalize sprint`, `revise <change>`, and `show approvals` as source-thread control phrases.
- Execution approval commands must stay locked until the user finalizes the sprint plan.
- Treat approvals as intent; never auto-send, auto-post, or auto-spend.

### Approval & Execution (the flywheel core)

The chat control phrases are no longer prompt-only concepts — they are backed by a persisted approval state machine. Run `approvals.py` as a tool to turn each command into a real, durable state transition against `data/sprint_state.json` (which lives beside the profile). The safety model is enforced in code: a draft sprint cannot approve or execute anything, and only approved items can be executed.

Map each chat command to its subcommand (every call takes `--profile <path>`):

| Chat command | Tool call |
|---|---|
| `show approvals` | `approvals.py status` |
| `finalize sprint` | `approvals.py finalize` (draft → finalized; unlocks execution) |
| `approve <section>` | `approvals.py approve <section>` (e.g. `launch`, `backlinks`, `outbound`, `content`, `creator`, `mpp_spend`) |
| `approve <id>` / per-item approve | `approvals.py approve <item_id>` |
| `approve all` | `approvals.py approve all` |
| `reject <id | section | all>` | `approvals.py reject <target>` |
| `execute <id>` / mark sent-posted-paid | `approvals.py execute <item_id>` |
| `execute approved` | `approvals.py execute approved` |

The flow is: **draft dashboard → review/edit → `finalize sprint` → `approve <section>`/`approve <id>` → `execute`.** Execution stays code-locked until `finalize sprint` runs; `approvals.py` returns exit 0 on success and exit 1 when blocked (e.g. approving inside a draft), and you relay its message to the thread.

**Learning loop:** each sprint's approvals are recorded to `data/sprint_history.jsonl` when the next sprint is compiled. `sprint_report.py` reads that history and orders next week's focus by which sections the founder actually approved before — Flywheel proposes more of what gets greenlit and less of what gets rejected.

## Flywheel Help Message

If a user says `help`, `commands`, `capabilities`, or `what can you do?`, respond with a compact menu before doing any sprint work:

```text
I’m Flywheel — your GTM employee.

I can:
- Draft weekly acquisition sprints
- Find launch channels
- Find backlink/listing opportunities
- Score outbound targets and draft messages
- Plan creator campaigns and spend requests
- Draft trend-based content
- Walk you through a sprint before finalizing it

Start with:
Run a GTM sprint for <product>. ICP: <buyer>. Competitors: <names>. Budget: <$>. Focus: <channels>.

Review commands:
help | review launch | review backlinks | review outbound | review content | review mpp spend | review budget | start walkthrough | approve <section> | edit <section>: <change> | finalize sprint | show approvals

Safety: I won’t send, post, or spend without explicit approval.
```

## Verification Steps

After running the full sequence:

```bash
python skills/flywheel-agent/scripts/validate_outputs.py
```

Expected outputs:
- Valid product profile in `data/product_profile.json`
- At least 6 launch actions in launch plan
- At least 5 opportunities with scores
- All outbound/spend items marked "approval_required: true"
- Complete weekly sprint report generated
- No secrets or credentials in output files

## Triggers

Respond to these phrases by loading this skill:
- "start my acquisition flywheel"
- "run GTM sprint" / "run my GTM sprint"
- "find first customers"
- "launch-max this product"
- "creator campaign" / "influencer campaign"
- "weekly acquisition sprint"
- "customer acquisition flywheel"

## Sample Usage

```
User: "Start my acquisition flywheel for ExampleAI"
Flywheel: Runs intake → generates product profile → launch plan →
         backlinks → outbound → creators → sprint report
User: Reviews recommendations and approves specific actions
Flywheel: Executes only approved items with safety gates
```

## Output Structure

The final sprint report includes:
- **Launch Actions** (5-8 channels with tailored copy)
- **Backlink Opportunities** (10+ targets with outreach drafts)
- **Warm Outbound Queue** (personalized messages, approval-gated)
- **Creator Campaign** (influencer brief + spend requests)
- **Trend Content** (5+ social posts tied to current trends)
- **Spend Summary** (all proposed spend with approval gates)
- **Next Week Plan** (compound learnings into next sprint)

## Safety Gates & Pitfalls

**Critical Safety Rules:**
- Never auto-send messages, DMs, emails, or posts
- Never auto-spend money or execute payments
- Always mark external actions as requiring approval
- Validate all competitor URLs before using
- For live user requests, do real research and/or parse founder-provided context before generating outputs
- Use the ExampleAI fixture only when the user explicitly asks for a demo/test fixture or when running CI
- Never present fixture output as if it were tailored to the user's product

**Common Pitfalls:**
- Web search rate limits → fall back to cached research from earlier in the same sprint, or tell the user research is delayed
- Running a research-stage script without `--input` → it exits 2 with an actionable message; supply `--input <research.json>` (or `--demo` only for explicit demos)
- Missing live API/search access → tell the user what's blocked and what input is needed; never fill the gap with fixture data
- Competitor URLs broken → validate before processing
- Budget not specified → default to safe values ($100/week, $25/action)
- No approval confirmation → always require explicit "yes" for spend/send

## Example Commands

Once skill is loaded, use these exact commands:

```bash
# Full sprint generation
"Run my weekly GTM sprint for [product name]"

# Individual loops
"Generate launch plan for [product]"
"Find backlink opportunities for [competitors]"
"Create creator campaign for [niche]"
"Draft warm outbound for [leads]"

# Validation
"Validate my flywheel outputs"
"Show me what needs approval"
```