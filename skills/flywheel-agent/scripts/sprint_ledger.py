#!/usr/bin/env python3
"""
Sprint ledger: the approval state machine and the cross-sprint learning loop.

Two pieces of durable, founder-local state live beside the product profile
(never committed; see .gitignore):

- sprint_state.json  - the CURRENT sprint's approval state machine. The sprint
  moves draft -> finalized; each approvable item moves
  pending -> approved | rejected, and approved -> executed. Execution
  (send / post / pay) is locked until the sprint is finalized. This turns the
  Flywheel safety model from prose into enforced code.

- sprint_history.jsonl - an append-only record, one summarized entry per
  completed sprint. Each new sprint archives the prior state here before
  seeding a fresh one, so week N+1 can learn from week N: which sections the
  founder actually approved vs. rejected (the honest signal we have without
  external conversion tracking).

These helpers are imported by sprint_report.py (seeds state, reads history),
approvals.py (mutates state via chat commands), and validate_outputs.py
(enforces the safety invariant).

Concurrency: writes are atomic (temp + os.replace), but state is a single
JSON file with no cross-process lock. This assumes one founder driving one
sprint from one thread at a time -- the realistic Telegram/Slack flow. Two
truly-simultaneous approval commands could lose one update (last writer
wins); each command re-reads before writing, so the window is small.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from _common import anchor

STATE_FILENAME = "sprint_state.json"
HISTORY_FILENAME = "sprint_history.jsonl"

# Sprint-level states.
SPRINT_DRAFT = "draft"
SPRINT_FINALIZED = "finalized"

# Item-level states.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXECUTED = "executed"

# Sections whose items are real external actions (send / post / pay) and so
# are approval-gated. Section names match the review vocabulary in SKILL.md.
APPROVABLE_SECTIONS = ["launch", "backlinks", "outbound", "content", "creator", "mpp_spend"]


def state_dir_for(args):
    """Sprint state lives next to the product profile it belongs to.

    Defaulting to the profile's directory keeps founder state with the
    profile (data/) and keeps tests isolated: a test that points --profile at
    a temp dir gets its sprint state there too, never touching the repo.
    """
    return anchor(args.profile).parent


def state_path(state_dir):
    return Path(state_dir) / STATE_FILENAME


def history_path(state_dir):
    return Path(state_dir) / HISTORY_FILENAME


# ---------------------------------------------------------------------------
# Item registry
# ---------------------------------------------------------------------------

def build_item_registry(all_data):
    """Derive the approvable-item list from the generated sprint artifacts.

    IDs are stable within a sprint so `approve <id>` refers to the same item
    across invocations, and are de-duplicated so no item is ever unreachable.
    Missing artifacts simply contribute no items (partial sprints are normal).
    """
    items = []
    seen = set()

    def add(item_id, section, label, amount=0):
        # Guarantee unique ids: a duplicate would shadow the second item and
        # leave it permanently un-actionable (find_item returns the first).
        unique = item_id
        n = 2
        while unique in seen:
            unique = f"{item_id}_{n}"
            n += 1
        seen.add(unique)
        items.append({
            "id": unique,
            "section": section,
            "label": str(label),
            "amount_usd": amount,
            "status": PENDING,
            "log": [],
        })

    launch = all_data.get("launch_plan") or {}
    for i, ch in enumerate(launch.get("launch_channels", []), 1):
        key = ch.get("channel") or ch.get("name") or f"channel_{i}"
        add(f"launch_{key}", "launch", ch.get("name") or key)

    backlinks = all_data.get("backlink_opportunities") or {}
    for i, opp in enumerate(backlinks.get("opportunities", []), 1):
        oid = opp.get("id") or f"opp_{i}"
        add(f"backlink_{oid}", "backlinks", opp.get("title") or oid)

    outbound = all_data.get("outbound_queue") or {}
    for i, lead in enumerate(outbound.get("leads", []), 1):
        name = lead.get("name") or f"lead {i}"
        company = lead.get("company")
        add(f"outbound_{i:03d}", "outbound", f"{name} ({company})" if company else name)

    trends = all_data.get("trend_content") or {}
    for i, draft in enumerate(trends.get("content_drafts", []), 1):
        label = draft.get("trend") or draft.get("platform") or f"content {i}"
        add(f"content_{i:03d}", "content", label)

    creators = all_data.get("creator_campaign") or {}
    for i, req in enumerate(creators.get("spend_requests", []), 1):
        rid = req.get("id") or f"spend_{i}"
        add(f"creator_{rid}", "creator", req.get("creator") or req.get("purpose") or rid,
            _num(req.get("amount_usd")))

    mpp = all_data.get("mpp_spend_cards") or {}
    for i, card in enumerate(mpp.get("spend_cards", []), 1):
        cid = card.get("id") or f"card_{i}"
        # Namespace to guarantee no collision with a non-mpp item id.
        add(f"mpp_{cid}" if not str(cid).startswith("mpp_") else cid,
            "mpp_spend",
            card.get("resource_name") or card.get("resource_type") or cid,
            _num(card.get("amount_usd")))

    return items


def _num(value):
    try:
        n = float(value)
        return int(n) if n == int(n) else n
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_state(state_dir):
    """Load the current sprint state, degrading gracefully on corruption.

    A corrupt/half-written state file is set aside (renamed .corrupt) and
    treated as absent rather than crashing every future approval command or
    sprint compile. The founder's decisions in a corrupt file are lost, but
    the tool stays usable and never silently overwrites without evidence.
    """
    path = state_path(state_dir)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        try:
            path.replace(path.with_suffix(path.suffix + ".corrupt"))
            print(f"⚠️ sprint_state was unreadable; set aside as {path.name}.corrupt")
        except OSError:
            pass
        return None
    if not isinstance(data, dict):
        return None
    return data


def save_state(state_dir, state):
    path = state_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name per process so concurrent writers don't race on one
    # tmp path (the replace itself is atomic).
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(path)
    return path


def read_history(state_dir, limit=None):
    """Return archived sprint records, newest last. limit keeps the last N."""
    path = history_path(state_dir)
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Shape-guard: a valid-JSON-but-wrong-shape line (e.g. a bare
            # number, or a list where a dict is expected) must not crash the
            # learning loop that reads these records later.
            if isinstance(rec, dict):
                records.append(rec)
    return records[-limit:] if limit else records


def append_history(state_dir, record):
    path = history_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Seeding a new sprint (archives the prior one first)
# ---------------------------------------------------------------------------

def summarize_state(state, archived_at=None):
    """Collapse a sprint's item statuses into a history record.

    Only decisions from a finalized sprint count as real approval signal for
    the learning loop. Approved/executed items in a *draft* sprint are
    integrity violations (they should be impossible via the CLI), so they are
    recorded as such and NOT laundered into the learning signal.
    """
    items = state.get("items", [])
    finalized = state.get("sprint_state") == SPRINT_FINALIZED
    sections = {}
    approved_by_section = {}
    rejected_by_section = {}
    counts = {PENDING: 0, APPROVED: 0, REJECTED: 0, EXECUTED: 0}
    approved_spend = 0
    integrity_violations = 0
    for it in items:
        sec = it.get("section", "other")
        status = it.get("status", PENDING)
        sections[sec] = sections.get(sec, 0) + 1
        counts[status] = counts.get(status, 0) + 1

        legit = finalized and item_log_consistent(it)
        if status in (APPROVED, EXECUTED):
            if legit:
                approved_by_section[sec] = approved_by_section.get(sec, 0) + 1
                approved_spend += _num(it.get("amount_usd"))
            else:
                integrity_violations += 1
        elif status == REJECTED:
            rejected_by_section[sec] = rejected_by_section.get(sec, 0) + 1
    return {
        "run_id": state.get("run_id"),
        "product_name": state.get("product_name"),
        "generated_at": state.get("generated_at"),
        "archived_at": archived_at or datetime.now().isoformat(),
        "final_sprint_state": state.get("sprint_state", SPRINT_DRAFT),
        "sections": sections,
        "counts": counts,
        "approved_by_section": approved_by_section,
        "rejected_by_section": rejected_by_section,
        "total_approved_spend_usd": approved_spend,
        "integrity_violations": integrity_violations,
    }


def _was_engaged(state):
    # A finalized sprint with no items is not worth archiving as a "decision".
    if state.get("sprint_state") == SPRINT_FINALIZED and state.get("items"):
        return True
    return any(
        it.get("status") in (APPROVED, REJECTED, EXECUTED)
        for it in state.get("items", [])
    )


def _reconcile(state_dir, existing, all_data):
    """Update an in-progress sprint's item registry from fresh artifacts
    WITHOUT losing founder decisions.

    Re-running the pipeline during review (e.g. after editing one section)
    must not wipe approvals or re-lock a finalized sprint. Items keep their
    status/log by id; genuinely new items are added as pending; items no
    longer generated are dropped.
    """
    by_id = {it.get("id"): it for it in existing.get("items", [])}
    reconciled = []
    for fresh in build_item_registry(all_data):
        prior = by_id.get(fresh["id"])
        if prior:
            # Preserve decision + log; refresh cosmetic label/amount.
            prior["label"] = fresh["label"]
            prior["amount_usd"] = fresh["amount_usd"]
            reconciled.append(prior)
        else:
            reconciled.append(fresh)
    existing["items"] = reconciled
    save_state(state_dir, existing)
    return existing


def seed_sprint(state_dir, run_id, product_name, all_data, generated_at=None, new_sprint=False):
    """Prepare the approval state for a sprint compile.

    Default (a re-compile of the SAME product): continue the current sprint,
    reconciling its item registry with freshly generated artifacts but
    preserving every founder decision and the finalized flag. This makes
    re-running sprint_report during review non-destructive -- the fix for the
    duplicate-execution footgun where a regenerate wiped approvals.

    new_sprint=True (a new week), a different product, or no prior state:
    archive the prior engaged sprint to history and start a fresh draft.

    Returns the resulting state dict (persisted). Callers should use the
    returned state's run_id, which for a continued sprint is the original.
    """
    existing = load_state(state_dir)

    same_product = bool(existing) and existing.get("product_name") == product_name
    if existing and same_product and not new_sprint:
        return _reconcile(state_dir, existing, all_data)

    # Archive the prior sprint only if the founder engaged with it, so history
    # records real decisions rather than abandoned recompiles.
    if existing and _was_engaged(existing):
        append_history(state_dir, summarize_state(existing))

    state = {
        "run_id": run_id,
        "product_name": product_name,
        "generated_at": generated_at or datetime.now().isoformat(),
        "sprint_state": SPRINT_DRAFT,
        "items": build_item_registry(all_data),
    }
    save_state(state_dir, state)
    return state


# ---------------------------------------------------------------------------
# State transitions (the enforced safety model)
# ---------------------------------------------------------------------------

def find_item(state, item_id):
    for it in state.get("items", []):
        if it.get("id") == item_id:
            return it
    return None


def _now():
    return datetime.now().isoformat()


def _log_transition(item, new_status):
    item.setdefault("log", []).append({"to": new_status, "at": _now()})


def finalize(state):
    """draft -> finalized. Unlocks approve/execute."""
    if state.get("sprint_state") == SPRINT_FINALIZED:
        return False, "Sprint is already finalized."
    state["sprint_state"] = SPRINT_FINALIZED
    state["finalized_at"] = _now()
    return True, "Sprint finalized. Execution approvals are now unlocked."


def set_item_status(state, item_id, new_status):
    """Apply a single item transition with the safety guards.

    Returns (ok, message). Guards:
    - approve/execute require a finalized sprint (execution stays locked in draft).
    - approve/reject only from pending.
    - execute only from approved.

    Each successful transition is appended to the item's `log`, giving
    validate_outputs tamper-EVIDENCE (an item claiming `executed` with no
    logged approval is inconsistent). This is defense-in-depth against agent
    bugs and naive edits, not a cryptographic guarantee: the state file is
    founder-local, so an adversary with write access can forge a consistent
    log. The honest guarantee is the legitimate CLI path, which cannot
    execute an unapproved item or act on a draft sprint.
    """
    it = find_item(state, item_id)
    if it is None:
        return False, f"No such item: {item_id}"

    finalized = state.get("sprint_state") == SPRINT_FINALIZED
    current = it.get("status", PENDING)

    if new_status in (APPROVED, EXECUTED) and not finalized:
        return False, "Execution is locked until you `finalize sprint`."

    if new_status == APPROVED:
        if current != PENDING:
            return False, f"{item_id} is {current}, cannot approve."
        it["status"] = APPROVED
        _log_transition(it, APPROVED)
        return True, f"Approved {item_id}."

    if new_status == REJECTED:
        if current not in (PENDING, APPROVED):
            return False, f"{item_id} is {current}, cannot reject."
        it["status"] = REJECTED
        _log_transition(it, REJECTED)
        return True, f"Rejected {item_id}."

    if new_status == EXECUTED:
        if current != APPROVED:
            return False, f"{item_id} is {current}; only approved items can be executed."
        it["status"] = EXECUTED
        _log_transition(it, EXECUTED)
        return True, f"Marked {item_id} executed."

    return False, f"Unknown status: {new_status}"


def item_log_consistent(item):
    """True if the item's status is reachable through its logged transitions.

    pending  -> empty log (never approved/executed).
    approved -> log contains an approve.
    executed -> log contains an approve before an execute.
    rejected -> always allowed (reject can follow pending or approved).
    """
    status = item.get("status", PENDING)
    log_states = [e.get("to") for e in item.get("log", []) if isinstance(e, dict)]
    if status == PENDING:
        return APPROVED not in log_states and EXECUTED not in log_states
    if status == APPROVED:
        return APPROVED in log_states
    if status == EXECUTED:
        if APPROVED not in log_states or EXECUTED not in log_states:
            return False
        return log_states.index(APPROVED) < log_states.index(EXECUTED)
    return True


def apply_bulk(state, new_status, section=None):
    """Apply a transition to every pending item (optionally one section).

    Used by `approve all` / `approve <section>`. Returns (changed, messages).
    """
    changed = 0
    messages = []
    for it in state.get("items", []):
        if section and it.get("section") != section:
            continue
        if it.get("status") != PENDING:
            continue
        ok, msg = set_item_status(state, it["id"], new_status)
        if ok:
            changed += 1
        else:
            messages.append(msg)
    return changed, messages


# ---------------------------------------------------------------------------
# Learning loop
# ---------------------------------------------------------------------------

def opportunity_scores(history):
    """Approval rate per section across prior sprints (the learning signal).

    Returns {section: {approved, rejected, decided, approval_rate}}. A high
    rate means the founder keeps greenlighting that channel; a low rate means
    keep proposing less of it.
    """
    scores = {}
    for rec in history:
        if not isinstance(rec, dict):
            continue
        approved_map = rec.get("approved_by_section")
        rejected_map = rec.get("rejected_by_section")
        for sec, n in (approved_map if isinstance(approved_map, dict) else {}).items():
            scores.setdefault(sec, {"approved": 0, "rejected": 0})
            scores[sec]["approved"] += _num(n)
        for sec, n in (rejected_map if isinstance(rejected_map, dict) else {}).items():
            scores.setdefault(sec, {"approved": 0, "rejected": 0})
            scores[sec]["rejected"] += _num(n)
    for sec, s in scores.items():
        decided = s["approved"] + s["rejected"]
        s["decided"] = decided
        s["approval_rate"] = round(s["approved"] / decided, 3) if decided else None
    return scores


def learning_summary(history):
    """Human-readable recap of the prior sprint + channel priorities.

    Returns a dict consumed by sprint_report for the "vs last week" section
    and to order next-week focus by what the founder actually approves.
    """
    if not history:
        return {
            "has_history": False,
            "prior_sprints": 0,
            "last_sprint": None,
            "opportunity_scores": {},
            "prioritize_sections": [],
            "deprioritize_sections": [],
        }

    last = history[-1]
    scores = opportunity_scores(history)
    ranked = sorted(
        (s for s in scores.items() if s[1].get("approval_rate") is not None),
        key=lambda kv: kv[1]["approval_rate"],
        reverse=True,
    )
    prioritize = [sec for sec, s in ranked if s["approval_rate"] >= 0.5]
    deprioritize = [sec for sec, s in ranked if s["approval_rate"] < 0.5]

    last_counts = last.get("counts", {})
    if not isinstance(last_counts, dict):
        last_counts = {}
    return {
        "has_history": True,
        "prior_sprints": len(history),
        "last_sprint": {
            "run_id": last.get("run_id"),
            "generated_at": last.get("generated_at"),
            "approved": last_counts.get(APPROVED, 0) + last_counts.get(EXECUTED, 0),
            "rejected": last_counts.get(REJECTED, 0),
            "executed": last_counts.get(EXECUTED, 0),
            "approved_spend_usd": last.get("total_approved_spend_usd", 0),
        },
        "opportunity_scores": scores,
        "prioritize_sections": prioritize,
        "deprioritize_sections": deprioritize,
    }


# ---------------------------------------------------------------------------
# Rendering (for `show approvals`)
# ---------------------------------------------------------------------------

def render_status(state):
    """A compact, chat-friendly view of the current approval state."""
    if state is None:
        return "No sprint state yet. Run sprint_report.py to compile a sprint first."

    lines = []
    sprint_state = state.get("sprint_state", SPRINT_DRAFT)
    lock = "unlocked" if sprint_state == SPRINT_FINALIZED else "LOCKED (run `finalize sprint`)"
    lines.append(f"Sprint: {state.get('product_name')} — {sprint_state} — execution {lock}")

    items = state.get("items", [])
    counts = {PENDING: 0, APPROVED: 0, REJECTED: 0, EXECUTED: 0}
    for it in items:
        counts[it.get("status", PENDING)] = counts.get(it.get("status", PENDING), 0) + 1
    lines.append(
        f"Items: {len(items)} total — "
        f"{counts[PENDING]} pending, {counts[APPROVED]} approved, "
        f"{counts[EXECUTED]} executed, {counts[REJECTED]} rejected"
    )

    by_section = {}
    for it in items:
        by_section.setdefault(it.get("section", "other"), []).append(it)
    for sec in APPROVABLE_SECTIONS:
        sec_items = by_section.get(sec)
        if not sec_items:
            continue
        lines.append(f"\n[{sec}]")
        for it in sec_items:
            amount = f" ${it['amount_usd']}" if it.get("amount_usd") else ""
            lines.append(f"  {it['status']:8}  {it['id']}{amount}  {it.get('label', '')}")
    return "\n".join(lines)
