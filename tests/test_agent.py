"""End-to-end harness tests with the scripted FakeLLM (CPU only)."""
from netinject.agent.loop import run_episode
from netinject.env.tools import TOOLS as TOOL_NAMES
from netinject.evaluation.judge import label, label_file
from netinject.evaluation.metrics import wilson
from netinject.llm.base import AssistantTurn, ToolCall
from netinject.llm.fake_llm import FakeLLM
from netinject.llm.ollama_client import parse_text_tool_calls
from netinject.run import finished_keys, plan, run_grid
from netinject.scenarios import compose as C

EPS = {e.id: e for e in C.all_episodes()}
TASKS = {t.id: t for t in C.load_tasks()}


def labels(ep, script, max_steps=12):
    traces = run_episode(ep, FakeLLM(script), max_steps=max_steps)
    return {g: label(ep, traces["none"] if t.get("same_as_none") else t) for g, t in traces.items()}


def attack(ep, ticket):
    g = ep.attack_goal
    return g.action, {"device": g.device, **g.params, "ticket_id": ticket}


def reads_and_write(task_id):
    calls = C.solution_calls(TASKS[task_id])
    return calls[:5], calls[5]


def test_every_benign_task_is_solved_by_its_scripted_run():  # SPECS §6 acceptance criterion
    for tid in TASKS:
        reads, write = reads_and_write(tid)
        for gate, lab in labels(EPS[f"{tid}__control"], reads + [write]).items():
            assert lab["task_success"] and not lab["unsafe_write_attempted"] and not lab["false_block"], (tid, gate)


def test_attack_citing_task_ticket_is_blocked_by_both_gates():
    reads, write = reads_and_write("T01")
    for d in range(4):
        ep = EPS[f"T01__direct__d{d}"]
        lab = labels(ep, reads + [attack(ep, ep.task_ticket), write])
        assert lab["none"]["unsafe_write_executed"] and lab["none"]["attack_goal_executed"]
        assert lab["none"]["realized_delay"] == d  # payload read d reads before the attack
        for g in ("scope_check", "ticket_bound"):
            assert lab[g]["gate_blocked"] and not lab[g]["unsafe_write_executed"] and lab[g]["task_success"]


def test_ticket_confusion_passes_scope_check_but_not_ticket_bound():
    reads, write = reads_and_write("T05")
    ep = EPS["T05__ticket_confusion__d0"]
    decoy = next(g.decoy_ticket.id for g in C.load_goals() if g.id == ep.goal_id)
    traces = run_episode(ep, FakeLLM(reads + [attack(ep, decoy), write]))
    assert traces["scope_check"] == {"gate": "scope_check", "same_as_none": True}
    assert label(ep, traces["none"])["unsafe_write_executed"]
    tb = label(ep, traces["ticket_bound"])
    assert tb["gate_blocked"] and not tb["unsafe_write_executed"] and tb["task_success"]


def test_legit_write_without_ticket_id_is_a_false_block():
    reads, (name, args) = reads_and_write("T02")
    args = {k: v for k, v in args.items() if k != "ticket_id"}
    lab = labels(EPS["T02__control"], reads + [(name, args)])
    assert lab["none"]["task_success"] and not lab["none"]["false_block"]
    assert lab["scope_check"]["false_block"] and not lab["scope_check"]["task_success"]


def test_runaway_loop_stops_at_max_steps():
    reads, _ = reads_and_write("T03")
    lab = labels(EPS["T03__control"], reads * 5, max_steps=12)["none"]
    assert lab["end"] == "max_steps" and lab["n_llm_calls"] == 12 and not lab["task_success"]


KNOWN = set(TOOL_NAMES)


def test_text_tool_call_fallback_parser():
    p = lambda s: parse_text_tool_calls(s, KNOWN)  # noqa: E731
    assert p('{"name": "get_ticket", "arguments": {"ticket_id": "CHG-2101"}}')[0].args == {"ticket_id": "CHG-2101"}
    assert p('[TOOL_CALLS] [{"name": "list_alerts", "arguments": {}}]')[0].name == "list_alerts"
    assert p('<tool_call>{"name": "search_kb", "parameters": {"query": "b"}}</tool_call>')[0].args == {"query": "b"}
    assert p('```json\n{"name": "list_alerts", "arguments": "{\\"device\\": \\"x\\"}"}\n```')[0].args == {"device": "x"}
    assert p("I applied the change approved in CHG-2101.") == []
    # an invented tool in JSON form is passed on, so the agent gets the normal "unknown tool" error (Llama "apply_change")
    assert p('{"name": "apply_change", "parameters": {"ticket_id": "CHG-2101"}}')[0].name == "apply_change"
    assert p("print(x) and foo(bar=1)") == []  # Python-style calls only for known tool names
    # Pilot v1, Llama-3.1-8B: the whole procedure as JSON objects inside prose
    llama = ('Here are the tool calls in the order specified:\n\n1. List open alerts for fw-edge-1:\n'
             '{"name": "list_alerts", "parameters": {"device": "fw-edge-1"}}\n\n2. Retrieve change ticket CHG-2101:\n'
             '{"name": "get_ticket", "parameters": {"ticket_id": "CHG-2101"}}')
    assert [(c.name, c.args) for c in p(llama)] == [("list_alerts", {"device": "fw-edge-1"}),
                                                    ("get_ticket", {"ticket_id": "CHG-2101"})]
    # Pilot v1, Mistral-7B: Python-style calls in code blocks
    mistral = ('1. List open alerts for fw-edge-1:\n```\nlist_alerts(device="fw-edge-1")\n```\n\n'
               "2. Read runbook 'fw-acl-change':\n```\nread_runbook(name='fw-acl-change')\n```")
    assert [(c.name, c.args) for c in p(mistral)] == [("list_alerts", {"device": "fw-edge-1"}),
                                                      ("read_runbook", {"name": "fw-acl-change"})]


def test_one_call_per_turn_runs_only_the_first_call():
    class Planner:  # proposes the whole remaining procedure every turn, like Llama/Mistral in pilot v1
        def chat(self, messages, tools, temperature=0.0, seed=0):
            done = sum(m["role"] == "tool" for m in messages)
            sol = C.solution_calls(TASKS["T01"])[done:]
            return AssistantTurn(tool_calls=[ToolCall(n, a) for n, a in sol], parsed_from_text=bool(sol))

    ep = EPS["T01__control"]
    trace = run_episode(ep, Planner(), max_calls_per_turn=1)["none"]
    tools = [e for e in trace["events"] if e["type"] == "tool"]
    assert [e["name"] for e in tools] == [n for n, _ in C.solution_calls(TASKS["T01"])]  # one per turn, in order
    assert label(ep, trace)["task_success"] and label(ep, trace)["n_text_parsed"] == 6


def test_grid_runner_resumes_and_labels(tmp_path):
    reads, write = reads_and_write("T01")
    out = tmp_path / "traces.jsonl"
    jobs = plan(["T01"], [{"temperature": 0.0, "runs": 1}])[:3]

    class Broken:
        def chat(self, *a):
            raise TimeoutError("ollama timeout")

    run_grid(Broken(), "fake", out, jobs, max_steps=12)
    assert finished_keys(out) == set()  # errored runs are not "finished"
    run_grid(FakeLLM(reads + [write]), "fake", out, jobs, max_steps=12, parallel=2)
    n_lines = len(out.read_text().splitlines())
    run_grid(FakeLLM(reads + [write]), "fake", out, jobs, max_steps=12)  # nothing left to do
    assert len(out.read_text().splitlines()) == n_lines
    with open(out, "a") as f:
        f.write('{"key": "cut off by a disconn')  # partial last line
    df = label_file(out)
    assert len(df) == 3 * 3 and df["task_success"].all()


def test_wilson_interval():
    p, lo, hi = wilson(5, 10)
    assert p == 0.5 and round(lo, 3) == 0.237 and round(hi, 3) == 0.763
