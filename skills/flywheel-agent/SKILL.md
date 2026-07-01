---
name: flywheel-agent
description: Run a weekly customer acquisition flywheel sprint for founders.
version: 0.1.0
platforms: [linux, macos]
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

Run these scripts only after you have real product context. Do **not** run the no-argument demo path for a real user request.

### 1. Intake & Profile Creation
```bash
cd skills/flywheel-agent/scripts
python flywheel_intake.py "Product: [name] ([url]) ICP: [buyer] Competitors: [2-5 names] Budget: [$ weekly] Focus: [priority]"
```
Creates or updates `data/product_profile.json` with normalized product context. For recorded demos/tests only, use `python flywheel_intake.py --demo`.

### 2. Launch Strategy Generation
```bash
python launch_plan.py
```
Generates launch-max plan for Product Hunt, HN, directories, communities.

### 3. Backlink & Listing Discovery
```bash
python backlink_hunter.py
```
Finds competitor backlinks and listing opportunities via web search.

### 4. Lead Scoring & Warm Outbound
```bash
python lead_scorer.py
```
Scores leads and drafts personalized messages (if leads CSV provided).

### 5. Creator Campaign Planning
```bash
python creator_campaign.py
```
Plans influencer partnerships with performance incentives and spend requests.

### 6. Trend Analysis & Content
```bash
python trend_scan.py
```
Generates trend-based content and weekly social media drafts.

### 7. Sprint Report Compilation
```bash
python sprint_report.py
```
Compiles everything into `output/weekly_flywheel_sprint.md`.

## Slack / Telegram / Thread-Native Mode

When the sprint is triggered from Slack or Telegram:

- Acknowledge in the source thread/chat.
- Keep routine progress quiet unless there is a blocker.
- Never expose internal implementation notes such as reading scripts, checking files, running intake, demo-mode warnings, sample-data caveats, fixture names, or fallback datasets in the user-facing reply.
- For live product prompts, use the founder-provided product, ICP, competitors, budget, and focus as the only product context. Do not compare it to or warn about any demo fixture.
- Return a **draft review dashboard** by default, not a final/execution-ready sprint.
- Offer `start walkthrough` when the user wants a sequential section-by-section review.
- Use `review launch`, `review backlinks`, `review outbound`, `review content`, `review mpp spend`, `review budget`, `approve <section>`, `edit <section>: <change>`, `finalize sprint`, `revise <change>`, and `show approvals` as source-thread control phrases.
- Execution approval commands must stay locked until the user finalizes the sprint plan.
- Treat approvals as intent; never auto-send, auto-post, or auto-spend.

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
python validate_outputs.py
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
- Web search rate limits → fall back to cached research
- Missing live API/search access → explain the blocker or use explicit `--demo`; do not silently use fixture data
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