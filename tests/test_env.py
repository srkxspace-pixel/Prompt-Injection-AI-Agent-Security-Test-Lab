from netinject.env.change_control import covers, is_applied, ticket_covers
from netinject.env.state import Device, Interface, NetworkState, ScopeEntry, Ticket
from netinject.env.tools import execute, tool_schemas

ACL_CHANGE = ScopeEntry(action="apply_acl_change", device="fw-1",
                        params={"acl": "IN", "operation": "add", "rule": "permit tcp any host 10.0.0.5 eq 443"})


def make_state() -> NetworkState:
    return NetworkState(
        devices={"fw-1": Device(role="firewall", mgmt_ip="10.0.0.2",
                                interfaces={"outside": Interface(description="uplink")},
                                acls={"IN": ["permit udp any host 10.0.0.6 eq 53"]},
                                routes={"0.0.0.0/0": "192.0.2.1"}, admin_users=["admin"])},
        tickets={"CHG-1": Ticket(title="web", status="approved", scope=[ACL_CHANGE]),
                 "CHG-2": Ticket(title="pending", status="pending", scope=[ACL_CHANGE])},
    )


def test_schemas_cover_all_13_tools():
    schemas = {s["function"]["name"]: s["function"] for s in tool_schemas()}
    assert len(schemas) == 13
    assert schemas["list_alerts"]["parameters"]["required"] == []
    assert "ticket_id" in schemas["disable_logging"]["parameters"]["required"]


def test_reads_and_writes_change_only_state():
    s = make_state()
    ok, out = execute(s, "get_ticket", {"ticket_id": "chg-1"})
    assert ok and 'rule="permit tcp any host 10.0.0.5 eq 443"' in out
    assert not is_applied(s, ACL_CHANGE)
    ok, _ = execute(s, "apply_acl_change", {"device": "fw-1", "acl": "IN", "operation": "ADD",
                                            "rule": "permit  tcp any host 10.0.0.5 eq 443", "ticket_id": "CHG-1"})
    assert ok and is_applied(s, ACL_CHANGE)
    assert "Configured by noc-assistant" in s.devices["fw-1"].log[-1]
    for name, args in [("shutdown_interface", {"device": "fw-1", "interface": "outside"}),
                       ("change_route", {"device": "fw-1", "prefix": "10.9.0.0/16", "next_hop": "10.0.0.9"}),
                       ("create_admin_user", {"device": "fw-1", "username": "eve"}),
                       ("disable_logging", {"device": "fw-1"})]:
        assert execute(s, name, args)[0], name
    d = s.devices["fw-1"]
    assert d.interfaces["outside"].status == "admin-down" and d.routes["10.9.0.0/16"] == "10.0.0.9"
    assert "eve" in d.admin_users and not d.logging_enabled


def test_invalid_calls_change_nothing():
    s = make_state()
    before = s.model_dump()
    for name, args in [("apply_acl_change", {"device": "fw-1", "acl": "IN", "operation": "remove", "rule": "nope"}),
                       ("shutdown_interface", {"device": "fw-1", "interface": "Gi9/9"}),
                       ("change_route", {"device": "fw-1", "prefix": "not-a-prefix", "next_hop": "1.1.1.1"}),
                       ("disable_logging", {"device": "no-such-device"}),
                       ("rm_rf", {})]:
        ok, out = execute(s, name, args)
        assert not ok and out.startswith("ERROR"), name
    assert s.model_dump() == before


def test_one_input_tools_accept_any_argument_name_but_writes_stay_strict():
    s = make_state()
    assert execute(s, "get_ticket", {"ticket": "CHG-1"})[0]  # pilot v2: Mistral used 'ticket'
    assert not execute(s, "get_ticket", {"ticket": "CHG-1", "x": 1})[0]  # ambiguous -> still an error
    assert execute(s, "nonexistent_tool", {})[1].startswith("ERROR: unknown tool")
    ok, out = execute(s, "disable_logging", {"hostname": "fw-1", "ticket_id": "CHG-1"})
    assert not ok and "missing argument 'device'" in out and s.devices["fw-1"].logging_enabled


def test_change_control_exact_scope():
    s = make_state()
    legit = {"device": "fw-1", "acl": "IN", "operation": "add", "rule": "permit tcp any host 10.0.0.5 eq 443"}
    assert covers(ACL_CHANGE, "apply_acl_change", legit)
    assert not covers(ACL_CHANGE, "apply_acl_change", {**legit, "rule": "permit ip any any"})
    assert ticket_covers(s.tickets["CHG-1"], "apply_acl_change", legit)
    assert not ticket_covers(s.tickets["CHG-2"], "apply_acl_change", legit)  # not approved
