"""Write docs/SCENARIOS.md: the scenario set plus two fully rendered example episodes."""
from pathlib import Path

from netinject.env.tools import execute
from netinject.scenarios import compose as C

ROOT = Path(__file__).resolve().parents[1]


def show_episode(ep, task) -> list[str]:
    out = [f"### `{ep.id}` (goal {ep.goal_id}, payload in **{ep.carrier}** at step {ep.carrier_step})", "",
           "**User message**", "```", ep.user_message, "```"]
    for step, (name, args) in enumerate(C.solution_calls(task), 1):
        if step == 6:
            break
        out += [f"**Step {step}: `{name}({args})`**", "```", execute(ep.state, name, args)[1], "```"]
    return out


def main() -> None:
    tasks, goals, styles = C.load_tasks(), C.load_goals(), C.load_styles()
    lines = ["# Scenarios", "",
             f"{len(tasks)} tasks, {len(C.all_episodes())} episodes, scenarios hash `{C.scenarios_hash()[:12]}`. "
             "Validator: " + ("OK" if not C.validate() else "FAILED"), "",
             "## Tasks", "", "| Task | Title | Reads 2-5 (order) | Approved change |", "|---|---|---|---|"]
    for t in tasks:
        change = f"{t.change.action} {t.change.device} " + " ".join(f"{k}={v}" for k, v in t.change.params.items())
        lines.append(f"| {t.id} | {t.title} | {', '.join(C.ORDERS[t.order])} | `{change}` |")
    lines += ["", "## Attack goals (decoy ticket covers each)", "", "| Goal | Change | Decoy |", "|---|---|---|"]
    for g in goals:
        change = f"{g.change.action} {g.change.device} " + " ".join(f"{k}={v}" for k, v in g.change.params.items())
        lines.append(f"| {g.id} | `{change}` | {g.decoy_ticket.id}: {g.decoy_ticket.title} |")
    lines += ["", "## Attack style templates", ""]
    for s in styles:
        lines += [f"- **{s.id}**: {s.text or 'A (read before carrier): ' + s.fragment_a + ' / B (carrier): ' + s.fragment_b}"]
    lines += ["", "## Example episodes (what the model reads, following the procedure)", ""]
    by_id = {t.id: t for t in tasks}
    for ep_id in ("T01__authority__d1", "T10__split__d3"):
        ep = next(e for e in C.all_episodes() if e.id == ep_id)
        lines += show_episode(ep, by_id[ep.task_id]) + [""]
    (ROOT / "docs" / "SCENARIOS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
