from collections import Counter

from netinject.env.tools import execute
from netinject.scenarios import compose as C


def test_all_scenarios_valid():
    assert C.validate() == []


def test_grid_is_balanced():
    eps = C.all_episodes()
    attacks = [e for e in eps if e.style]
    assert len(eps) == 24 * 17 and len(attacks) == 24 * 16
    # delay is not confounded with artifact type: every (style, delay, carrier) cell has 24/4 = 6 tasks
    assert set(Counter((e.style, e.delay, e.carrier) for e in attacks).values()) == {6}
    # every style meets every goal
    assert all(len({e.goal_id for e in attacks if e.style == s}) == 5 for s in ("direct", "split"))
    assert all(e.carrier_step == 5 - e.delay for e in attacks)


def test_task_subsets_are_balanced():
    """The 12-task subsets in configs/grid.yaml keep delay unconfounded with artifact type."""
    from netinject.run import load_configs
    grid, _ = load_configs()
    pilot = set(grid["pilot"]["tasks"])
    for model, tasks in grid.get("tasks_overrides", {}).items():
        attacks = [e for e in C.all_episodes() if e.task_id in tasks and e.style]
        assert len(set(tasks)) == 12 and pilot <= set(tasks), model
        assert set(Counter((e.delay, e.carrier) for e in attacks).values()) == {12}, model
        assert all(len({e.goal_id for e in attacks if e.style == s}) == 5 for s in {e.style for e in attacks})


def test_payload_lands_in_carrier_read():
    task = C.load_tasks()[0]  # T01, order 0: ticket, log, runbook, kb
    goal = C.load_goals()[0]
    style = next(s for s in C.load_styles() if s.id == "ticket_confusion")
    ep = C.compose(task, style, 2, goal)  # d=2 -> carrier is the read at step 3 = log
    assert ep.carrier == "log"
    out = execute(ep.state, "read_device_log", {"device": "fw-edge-1"})[1]
    assert "ticket_id=CHG-3101" in out and "disable_logging" in out
    assert "2. Retrieve change ticket CHG-2101" in ep.user_message


def test_validator_catches_broken_data(monkeypatch):
    tasks = C.load_tasks()
    broken = tasks[1].model_copy(update={"id": tasks[0].id})
    monkeypatch.setattr(C, "load_tasks", lambda: (tasks[0], broken) + tasks[2:])
    assert any("duplicate task id" in e for e in C.validate())
