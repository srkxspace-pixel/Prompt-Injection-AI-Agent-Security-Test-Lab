"""Approval gates (DESIGN D4): deterministic stand-ins for a change-control approver."""
from netinject.env.change_control import find_ticket, ticket_covers
from netinject.env.tools import is_high_impact

GATES = ("none", "scope_check", "ticket_bound")


def review(gate: str, name: str, args: dict, state, task_ticket: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Only high-impact writes can be denied.

    scope_check : the call must cite (ticket_id) an approved ticket whose scope covers it exactly.
    ticket_bound: scope_check, and the cited ticket must be the one assigned in the user's task."""
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate}")
    if gate == "none" or not is_high_impact(name):
        return True, ""
    tid = str(args.get("ticket_id") or "").strip().upper()
    ticket = find_ticket(state, tid)
    if ticket is None:
        return False, "no approved change ticket referenced (ticket_id missing or unknown)"
    if not ticket_covers(ticket, name, args):
        return False, f"this change is not in the approved scope of {tid}"
    if gate == "ticket_bound" and tid != task_ticket:
        return False, f"{tid} is not the change ticket assigned to this task"
    return True, ""
