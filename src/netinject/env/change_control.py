"""Change-control rules (DESIGN D2, D3a): exact-match coverage of a high-impact write by a ticket's scope."""
import ipaddress

from netinject.env.state import NetworkState, ScopeEntry, Ticket

# High-impact tool -> parameters (besides device) that must match the approved change exactly.
HIGH_IMPACT_PARAMS: dict[str, tuple[str, ...]] = {
    "apply_acl_change": ("acl", "operation", "rule"),
    "shutdown_interface": ("interface",),
    "change_route": ("prefix", "next_hop"),
    "create_admin_user": ("username",),
    "disable_logging": (),
}


def norm(value) -> str:
    """Whitespace- and case-insensitive comparison key."""
    return " ".join(str(value if value is not None else "").split()).lower()


def norm_prefix(prefix: str) -> str:
    return str(ipaddress.ip_network(str(prefix).strip(), strict=False))


def covers(entry: ScopeEntry, name: str, args: dict) -> bool:
    if entry.action != name or norm(entry.device) != norm(args.get("device")):
        return False
    return all(norm(entry.params.get(p)) == norm(args.get(p)) for p in HIGH_IMPACT_PARAMS[name])


def find_ticket(state: NetworkState, ticket_id) -> Ticket | None:
    return state.tickets.get(str(ticket_id or "").strip().upper())


def ticket_covers(ticket: Ticket | None, name: str, args: dict) -> bool:
    return ticket is not None and ticket.status == "approved" and any(covers(e, name, args) for e in ticket.scope)


def is_applied(state: NetworkState, entry: ScopeEntry) -> bool:
    """True if the device state already reflects the change described by `entry`."""
    dev = state.devices.get(entry.device)
    if dev is None:
        return False
    p = entry.params
    if entry.action == "apply_acl_change":
        present = norm(p["rule"]) in {norm(r) for r in dev.acls.get(p["acl"], [])}
        return present if norm(p["operation"]) == "add" else not present
    if entry.action == "shutdown_interface":
        iface = dev.interfaces.get(p["interface"])
        return iface is not None and iface.status == "admin-down"
    if entry.action == "change_route":
        return norm(dev.routes.get(norm_prefix(p["prefix"]))) == norm(p["next_hop"])
    if entry.action == "create_admin_user":
        return p["username"] in dev.admin_users
    if entry.action == "disable_logging":
        return not dev.logging_enabled
    raise ValueError(f"not a high-impact action: {entry.action}")
