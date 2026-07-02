#!/usr/bin/env python3
"""
Approvals: the Flywheel execution safety gate, as an agent tool.

The founder drives the sprint from Telegram/Slack with chat commands
(`finalize sprint`, `approve <id>`, `show approvals`, ...). This script is how
the agent turns those commands into durable state transitions against
data/sprint_state.json, with the safety guards enforced in code rather than
trusted to the prompt:

- Nothing can be approved or executed while the sprint is a draft.
- Only approved items can be executed (marked sent / posted / paid).
- Every transition is persisted so a later validate_outputs.py run can prove
  no execution happened without approval.

Usage (invoked by the agent):
    approvals.py status
    approvals.py finalize
    approvals.py approve <item_id | section | all>
    approvals.py reject  <item_id>
    approvals.py execute <item_id | approved>

Exit codes: 0 success, 1 error/blocked (agent should relay the message).
"""

import argparse
import sys
import traceback

import sprint_ledger as ledger
from _common import EXIT_ERROR, EXIT_OK, configure_stdout, DEFAULT_PROFILE_PATH


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Drive the Flywheel approval state machine from chat commands."
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_PATH,
        help="Product profile path; sprint state lives beside it.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show the current approval state (`show approvals`).")
    sub.add_parser("finalize", help="Lock the sprint; unlock execution approvals.")

    p_approve = sub.add_parser("approve", help="Approve an item, a section, or all.")
    p_approve.add_argument("target", help="item id, section name, or 'all'.")

    p_reject = sub.add_parser("reject", help="Reject an item or a section.")
    p_reject.add_argument("target", help="item id, section name, or 'all'.")

    p_exec = sub.add_parser("execute", help="Mark approved item(s) executed (sent/posted/paid).")
    p_exec.add_argument("target", help="item id or 'approved' for all approved items.")

    return parser


def _resolve_bulk(state, target):
    """Return ('item', id) / ('section', name) / ('all', None) / (None, None)."""
    if target == "all":
        return "all", None
    if ledger.find_item(state, target) is not None:
        return "item", target
    # Accept the chat spelling "mpp spend" as well as the section id "mpp_spend".
    normalized = target.strip().lower().replace(" ", "_")
    if normalized in ledger.APPROVABLE_SECTIONS:
        return "section", normalized
    return None, None


def cmd_status(state_dir):
    state = ledger.load_state(state_dir)
    print(ledger.render_status(state))
    return EXIT_OK


def cmd_finalize(state_dir, state):
    ok, msg = ledger.finalize(state)
    print(("✅ " if ok else "⚠️ ") + msg)
    if ok:
        ledger.save_state(state_dir, state)
    # Finalizing an already-finalized sprint is not an error the agent needs
    # to escalate; report and succeed.
    return EXIT_OK


def cmd_transition(state_dir, state, target, new_status):
    kind, value = _resolve_bulk(state, target)

    if new_status == ledger.EXECUTED and target == "approved":
        # Execute every currently-approved item.
        changed = 0
        blocked = []
        for it in list(state.get("items", [])):
            if it.get("status") == ledger.APPROVED:
                ok, msg = ledger.set_item_status(state, it["id"], ledger.EXECUTED)
                changed += 1 if ok else 0
                if not ok:
                    blocked.append(msg)
        return _finish_bulk(state_dir, state, changed, blocked, "executed")

    if kind == "item":
        ok, msg = ledger.set_item_status(state, value, new_status)
        print(("✅ " if ok else "❌ ") + msg)
        if ok:
            ledger.save_state(state_dir, state)
            return EXIT_OK
        return EXIT_ERROR

    if kind in ("section", "all"):
        changed, blocked = ledger.apply_bulk(state, new_status, section=value if kind == "section" else None)
        return _finish_bulk(state_dir, state, changed, blocked, new_status)

    print(f"❌ No such item, section, or target: {target}")
    print(f"   Sections: {', '.join(ledger.APPROVABLE_SECTIONS)}. Run `approvals.py status` to list items.")
    return EXIT_ERROR


def _finish_bulk(state_dir, state, changed, blocked, verb):
    if changed:
        ledger.save_state(state_dir, state)
        print(f"✅ {changed} item(s) {verb}.")
    if blocked:
        # The most common blocker is a locked (draft) sprint; surface it once.
        print("⚠️ " + blocked[0])
        return EXIT_ERROR if not changed else EXIT_OK
    if not changed:
        print("No matching pending items to update.")
    return EXIT_OK


def main():
    configure_stdout()
    args = build_arg_parser().parse_args()
    state_dir = ledger.state_dir_for(args)

    try:
        if args.command == "status":
            return cmd_status(state_dir)

        state = ledger.load_state(state_dir)
        if state is None:
            print("❌ No sprint to act on yet. Compile one with sprint_report.py first.")
            return EXIT_ERROR

        if args.command == "finalize":
            return cmd_finalize(state_dir, state)
        if args.command == "approve":
            return cmd_transition(state_dir, state, args.target, ledger.APPROVED)
        if args.command == "reject":
            return cmd_transition(state_dir, state, args.target, ledger.REJECTED)
        if args.command == "execute":
            return cmd_transition(state_dir, state, args.target, ledger.EXECUTED)

        print(f"❌ Unknown command: {args.command}")
        return EXIT_ERROR
    except Exception as exc:
        traceback.print_exc()
        print(f"❌ Approval error: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
