# Slack GTM Employee Demo

Flywheel should feel like a teammate you tag in Slack, not a dashboard you have to remember to open.

This doc borrows the useful pattern from OpenTag / Claude Tag style workflows:

```text
@agent mention -> scoped work request -> quiet execution -> draft review dashboard -> optional walkthrough -> finalized sprint -> execution approvals
```

For the hackathon, use Hermes' native Slack gateway rather than adding a separate OpenTag dispatcher. Hermes already supports Slack Socket Mode, threaded replies, app mentions, files, and the same Flywheel profile distribution.

## Demo Goal

Show a founder tagging their GTM employee in a Slack channel and getting a weekly acquisition sprint draft back in-thread.

```text
Founder:
@Flywheel run a GTM sprint for ExampleAI.
ICP: e-commerce founders.
Competitors: CartPilot, ShopFlow, GrowthDock.
Budget: $2k this week.
Focus: warm outbound + creator distribution.
```

Expected behavior:

1. Flywheel posts a short acknowledgement in-thread.
2. Routine generation progress stays quiet.
3. Flywheel returns a polished **draft review dashboard** in the same thread.
4. The user can review sections directly or choose a guided walkthrough.
5. The sprint must be finalized before any execution approvals unlock.
6. No outbound, posting, or spend action happens without explicit human approval.

## Thread-Native Response Contract

### Acknowledgement

```text
On it — I’ll draft the weekly GTM sprint and come back here with a review dashboard. Nothing will be finalized, sent, posted, or spent without approval.
```

### Help / Capabilities Menu

If the user says `help`, `commands`, `capabilities`, or `what can you do?`, Flywheel should reply with:

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

### Default Final Callback: Draft Dashboard

```text
📝 Draft GTM Sprint Ready — not finalized yet

I drafted the sprint. Pick a section to review, or ask me to walk you through it.

| Section | Status | Command |
|---|---|---|
| Launch channels | Draft | `review launch` |
| Backlink/listing opportunities | Draft | `review backlinks` |
| Outbound targets | Draft | `review outbound` |
| Content plan | Draft | `review content` |
| Stripe MPP spend cards | Draft | `review mpp spend` |
| Budget/spend gates | Draft | `review budget` |

Commands:
- `help`
- `review launch`
- `approve launch`
- `edit launch: <change>`
- `start walkthrough`
- `finalize sprint`
- `show approvals`

Execution approvals are locked until `finalize sprint`.
```

### Optional Walkthrough Mode

If the user replies `start walkthrough`, Flywheel switches to sequential review:

```text
Step 1/5: Launch channels

Recommended:
1. DevHunt — free, low effort
2. BetaList — free, email capture
3. Product Hunt prep — bigger launch moment

Reply `approve launch`, `edit launch: ...`, `skip launch`, or `show details`.
```

Then continue through:

1. Launch channels
2. Backlink/listing opportunities
3. Outbound targets
4. Content plan
5. Budget/spend gates

### Finalized Sprint Callback

After reviewed sections are approved and the user sends `finalize sprint`:

```text
✅ Sprint Plan Finalized

Approved sections:
- Launch channels
- Backlink/listing opportunities
- Content plan

Still requires explicit execution approval:
- Submit launch listings
- Send outreach messages
- Publish social content
- Approve MPP payment

Reply `execute 1`, `execute approved launch`, or `show execution gates`.
```

## Quiet Callback Policy

| Event | Slack behavior |
|---|---|
| Mention received | Short ack in thread |
| Intake and script progress | Audit-only / keep quiet |
| Validation details | Audit-only unless failed |
| Draft weekly sprint | Post dashboard in thread |
| Walkthrough requested | Post one section at a time |
| Plan finalized | Unlock execution approval gates |
| Errors | Post concise blocker + next step |

Quiet means no play-by-play of internal steps — it never means hiding data provenance. If a run is a demo on sample fixtures, or live research is blocked, Flywheel says so plainly in the thread.

## Review Commands

Use these commands in the same Slack thread:

| Command | Meaning |
|---|---|
| `help` / `commands` / `what can you do?` | Show capabilities, starting prompts, commands, and safety rules |
| `review launch` | Show launch-channel details |
| `review backlinks` | Show backlink/listing details |
| `review outbound` | Show outbound target details |
| `review content` | Show content plan details |
| `review mpp spend` | Show Stripe MPP cards, paid GTM resources, 402 challenges, and approval commands |
| `review budget` | Show budget/spend gate details |
| `approve <section>` | Approve a draft plan section, not execution |
| `edit <section>: <change>` | Revise one draft section |
| `start walkthrough` | Switch to guided section-by-section review |
| `finalize sprint` | Lock the reviewed sprint plan |
| `show approvals` | List remaining section reviews/finalization gates |

## Execution Approval Commands

Execution commands should only appear after `finalize sprint`.

| Command | Meaning |
|---|---|
| `execute 1` | Execute one approved action through the configured tool path |
| `execute approved launch` | Execute finalized launch actions only |
| `execute approved content` | Execute finalized content actions only |
| `show execution gates` | List external sends/posts/spend still blocked |

Approval commands should be treated as human intent, not automatic execution. Flywheel can mark items approved or prepare execution queues, but external sends/spend still require the configured real-world tool path.

## Run Ledger

Every sprint report writes a lightweight run ledger under:

```text
demo/demo-output/runs/latest_run.json
```

The ledger captures:

- run id
- source surface: demo or Slack
- product name
- generated artifacts
- quiet callback policy
- draft review commands
- audit notes

This gives the demo an auditable “employee work history” without adding a full dispatcher stack.

## Slack Setup Summary

1. Create/install a Slack app for Flywheel.
2. Enable Socket Mode.
3. Add bot scopes:
   - `chat:write`
   - `app_mentions:read`
   - `channels:history`
   - `channels:read`
   - `groups:history`
   - `im:history`
   - `im:read`
   - `im:write`
   - `users:read`
   - `files:read`
   - `files:write`
4. Subscribe to bot events:
   - `app_mention`
   - `message.channels`
   - `message.groups`
   - `message.im`
5. Put secrets in the Flywheel profile `.env`, not markdown:
   - `SLACK_BOT_TOKEN=xoxb-...`
   - `SLACK_APP_TOKEN=xapp-...`
   - `SLACK_ALLOWED_USERS=U...` strongly recommended
6. Run:

```bash
hermes -p flywheel-agent gateway run
```

## Hackathon Positioning

> Flywheel is an installable GTM employee. Add it to Slack, tag it like a teammate, and it turns product context into a draft weekly acquisition sprint you can review, edit, finalize, and then approve for execution.
