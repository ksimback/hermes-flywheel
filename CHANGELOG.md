# Changelog

## 0.4.1 — 2026-07-02

### Polish
- **Output-quality gate.** A new test scans the shipped demo markdown for the copy defects that make generated output look broken — unrendered template placeholders, leaked internal review notes, literal `None`/`undefined`, and the proof-point grammar splice — so a regression in founder-facing copy fails CI. Intentional mail-merge tokens (`{name}`, `[Your name]`) are allowed.
- **"Verify your install" README section**: three no-key commands (`flywheel.py doctor`, `run --demo`, `pytest`) that confirm a fresh clone works end to end.

## 0.4.0 — 2026-07-02

### Live integrations (with honest degradation)
- **Headless research (`research.py`).** For cron/headless runs with no interactive agent, this turns a real Serper web search into the `--input` JSON that `backlink_hunter.py` and `trend_scan.py` consume — real backlink/listing discovery and trend signal. With `SERPER_API_KEY` set it searches live; without it, it exits with an actionable message and never falls back to fixtures. (Warm leads stay on the CSV / agent path — a search API doesn't produce engagement data.)
- **Real Stripe test-mode (`stripe_client.py`).** When `STRIPE_API_KEY` is an `sk_test_` key, the MPP planner creates real test-mode PaymentIntents so the founder sees genuine authorization objects in their Stripe test dashboard. Intents are created unconfirmed/uncaptured (no charge), live keys are refused outright, and with no key the flow stays a labelled simulation. The validator enforces the honesty rule: an artifact must be `simulated: true` or explicitly `stripe_test_mode` — a bare `simulated: false` (which would imply an unlabelled live charge) fails.

### One-command experience (`flywheel.py`)
- `flywheel.py run --demo` runs the whole pipeline in one command; `flywheel.py run "Product: …"` runs a real sprint, using live research where available and cleanly skipping stages whose input is missing (a partial sprint, never faked). `flywheel.py doctor` reports Python version, script presence, and which optional keys are configured.

### Hardening (pre-merge adversarial review)
- **`--partial` validation downgrades by explicit type, never by text.** A partial (headless/real) sprint is legitimately smaller than the full demo, so `validate_outputs.py --partial` relaxes completeness thresholds — but only issues explicitly tagged `Completeness` are relaxed. Safety, approval, secret, and test-mode findings stay hard failures, so a data-injected string (e.g. a lead named "Expected Corp") can never spoof a safety issue into a warning, and a non-test-mode 402 challenge always fails.
- **`flywheel.py` never reports a crashed stage as success.** A stage that exits with a real error (not the exit-2 "no input, skipped" code) fails the whole run.
- Real Stripe test-mode intents (`pi_…`) now validate correctly (not only the simulated `pi_test_mpp_…` form); malformed search responses degrade instead of crashing; network clients catch `socket.timeout` on Python 3.8/3.9; and `md_safe` now defangs injected markdown links and headings in addition to code fences.

## 0.3.0 — 2026-07-02

### The flywheel is real (approval state machine + learning loop)
- **Approval state machine as code.** The chat commands (`finalize sprint`, `approve <section>`, `show approvals`, per-item approve/reject/execute) are now durable state transitions driven by a new `approvals.py` tool, not prompt-only concepts. A sprint moves `draft → finalized`; each item moves `pending → approved | rejected → executed`.
- **Safety model enforced, not just described.** Execution is code-locked until the founder runs `finalize sprint`: a draft sprint may have zero approved or executed items, and only approved items can be executed. `validate_outputs.py` fails if these invariants are violated — even if the state file is tampered with directly.
- **Weekly learning loop.** `sprint_report.py` now archives each engaged sprint to `data/sprint_history.jsonl` and orders next week's focus by which sections the founder actually approved before. The report gains a `learning` block (`opportunity_scores`, prioritize/deprioritize sections) and a "vs Last Sprint" recap. The `sprint_history` and `opportunity_scores` memory settings in `config.yaml` are now backed by real files instead of being aspirational.
- New shared module `sprint_ledger.py` owns the state + history model. State files (`data/sprint_state.json`, `data/sprint_history.jsonl`) are founder-local and gitignored.

### Hardening (pre-merge adversarial review)
- **Re-compiling a sprint is non-destructive.** Re-running `sprint_report.py` for the same product continues the current sprint and preserves founder approvals (previously it minted a new sprint and silently reset approvals — a duplicate-execution footgun). Starting a genuinely new week is now the explicit `--new-sprint` flag.
- **Tamper-evidence.** Each approval transition is logged; `validate_outputs.py` flags an item that claims `approved`/`executed` without a consistent log or with a duplicate id. Scoping is honest: the state file is founder-local and unauthenticated, so this is defense-in-depth against bugs and casual edits, not a guarantee against an adversary with write access — the real guarantee is the enforced CLI path.
- Corrupt/malformed state or history no longer crashes the pipeline (a bad state file is set aside as `.corrupt`; malformed history lines are skipped); item ids are de-duplicated; `approve "mpp spend"` (spaced) is accepted alongside `mpp_spend`; state writes use a per-process temp file.

## 0.2.0 — 2026-07-02

### Data provenance & honesty
- Rewrote SOUL.md / SKILL.md data policy: fixture data is only used for explicit demos; the agent must disclose when live research is unavailable and never present sample data as real research. Removed all instructions to conceal demo-mode/fixture usage from users.
- Non-demo runs of `backlink_hunter`, `lead_scorer`, `creator_campaign`, and `trend_scan` now **require agent-supplied research** (`--input <json>`) and exit with code 2 (with an actionable message) instead of silently emitting fixture data.
- Stripe MPP artifacts are now explicitly labeled `"simulated": true` in JSON and called out as simulated test-mode artifacts in Markdown.
- All artifacts carry a `data_source` field (`sample_fixture` / `agent_research` / `founder_csv` / `founder_input` / `profile_derived`), and `demo_mode` is derived from the actual profile instead of being hardcoded `true`.

### New CLI contract (agent-tool oriented)
Scripts are tools invoked by the Hermes agent from Telegram/Slack threads:
- Uniform flags on every pipeline script: `--profile`, `--output-dir`, `--input`, `--demo` (see `skills/flywheel-agent/scripts/_common.py`).
- All paths anchor to the repo root — scripts work from any working directory.
- Meaningful exit codes: 0 success, 1 error, 2 research input required.
- `lead_scorer` gains `--leads-csv` and auto-detects `data/leads.csv` / `data/prospects.csv`.

### Bug fixes
- **Windows support:** UTF-8 is forced on all file I/O and stdout/stderr; the pipeline previously crashed with `UnicodeEncodeError` on cp1252 consoles. `platforms` now includes windows.
- Sprint report printed a hardcoded `$25` max single spend regardless of profile; now propagates `budget.max_single_spend_usd`.
- `total_actions` now includes trend content and MPP spend cards.
- Intake's internal review disclaimers no longer leak into outbound/launch/creator/trend marketing copy (`positioning.proof_points` vs new `positioning.review_notes`).
- Outbound message grammar fix (proof points were spliced mid-sentence).
- Budget parsing understands `$2k` / `$1.5m` style amounts.
- Product-name extraction no longer swallows trailing lowercase words.
- The output validator's secret scan was a no-op on any file mentioning "example"; replaced with line-level regex detection of real credential shapes.
- Removed dead code (unused search-query generation, no-op template replace, pre-set scores); fixture constants are no longer mutated in place; stale hardcoded year removed.
- Impact estimates relabeled "illustrative" (they are planning heuristics, not forecasts).

### Hardening (pre-ship adversarial review)
- Sprint report no longer crashes on partial pipelines (missing upstream artifacts now produce a partial report).
- Creator spend requests are clamped to the founder's `max_single_spend_usd` guardrail and can only be clamped downward (a low creator rate previously *raised* the request above the base fee); zero/negative weekly budgets are rejected at intake.
- Untrusted research strings are neutralized before markdown embedding (fence-breakout/prompt-injection into the approval dashboard is no longer possible), and `approval_required` is forced `true` on all agent-supplied opportunities.
- Relative output paths are confined to the repo root (no `..` escape); file writes are atomic (temp + rename); run-ledger IDs include microseconds + PID to prevent same-second collisions.
- Secret scanning covers JSON artifacts, run ledgers, and the profile (not just markdown), with broader credential patterns (`sk-proj-…`, `github_pat_…`, unquoted assignments).
- Agent-supplied `--input` values are type-coerced safely (string numbers degrade instead of crashing); ragged CSV rows no longer crash the lead scorer.
- URL extraction no longer turns "$1.5k" or "v2.0" into product URLs; multi-word product names are preserved ("My Cool Tool" no longer truncates to "My").

### Packaging, tests, CI
- Added `pyproject.toml` (Python >=3.8, pytest as dev dependency).
- Added GitHub Actions CI: Linux/macOS/Windows × Python 3.9/3.12 (3.8 support is best-effort; hosted runners no longer provide it).
- Test suite rewritten: tests run the pipeline into an isolated temp directory (no more writing into committed `demo/demo-output/`), are independently runnable, and add unit tests for intake parsing plus regression tests for every bug above. 39 tests, green on Windows.
- Config drift reconciled across `.env.EXAMPLE`, `README.md`, and `distribution.yaml`; docs updated for the new contract.

## 0.1.0

- Initial public release.
