"""Build demo/data.js for the offline demo page demo/index.html, from results/ and the scenario files.

The page replays recorded runs; no model runs here. It holds the T=0 run of every episode for every model (all three
gate branches), the result tables from results/eval/ and the run manifests. Tool outputs are clipped for size.

Usage: PYTHONPATH=src python scripts/build_demo.py      then open demo/index.html in a browser
"""
import json

import pandas as pd

from netinject.evaluation.judge import read_records
from netinject.reporting.report import NAMES, ROOT
from netinject.scenarios.compose import all_episodes

EV, TRACES, OUT = ROOT / "results" / "eval", ROOT / "results" / "traces", ROOT / "demo" / "data.js"
MODELS = ["qwen25_7b", "llama31_8b", "mistral_7b"]
GATES = ["none", "scope_check", "ticket_bound"]
TABLES = ["table1_tools", "table2_delay", "table3_gates", "matched12_table2_delay", "matched12_table3_gates",
          "variability_summary", "style_carrier", "gates_by_style", "logit_delay", "format_quality", "mcnemar"]
LABELS = ["task_success", "attack_goal_attempted", "attack_goal_executed", "unsafe_write_executed", "gate_blocked",
          "false_block", "realized_delay"]
CLIP = 900


def slim(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e["type"] == "tool":
            out.append({"k": "tool", "s": e["step"], "name": e["name"], "args": e["args"], "ok": e["allowed"],
                        "why": e["reason"], "out": e["output"][:CLIP]})
        elif e["type"] == "assistant":
            out.append({"k": "llm", "s": e["step"], "text": (e.get("content") or "")[:CLIP],
                        "parsed": bool(e.get("parsed_from_text"))})
    return out


def main() -> None:
    eps = {e.id: e for e in all_episodes()}
    labels = pd.read_csv(ROOT / "results" / "labels" / "labels.csv")
    labels = labels[labels.temperature == 0].set_index(["model", "episode_id", "gate"])
    episodes, manifests = [], {}
    for m in MODELS:
        manifests[m] = json.loads((TRACES / m / "manifest.json").read_text(encoding="utf-8"))
        for r in read_records(TRACES / m / "traces.jsonl"):
            if r.get("error") is not None or r["temperature"] != 0:
                continue
            ep = eps[r["episode_id"]]
            gates = {}
            for g in GATES:
                t = r["traces"][g]
                lab = labels.loc[(m, ep.id, g)]
                gates[g] = {"same": bool(t.get("same_as_none")), "fork": t.get("forked_at_step"),
                            "events": [] if t.get("same_as_none") else slim(t["events"]),
                            **{k: (None if pd.isna(lab[k]) else lab[k].item()) for k in LABELS}}
            episodes.append({"model": m, "id": ep.id, "task": ep.task_id, "style": ep.style or "control",
                             "delay": ep.delay, "carrier": ep.carrier, "carrier_step": ep.carrier_step,
                             "payload": ep.payload, "ticket": ep.task_ticket, "user": ep.user_message,
                             "approved": str(ep.approved_change), "goal": str(ep.attack_goal) if ep.attack_goal else None,
                             "origin": r.get("reused_from", "kaggle"), "gates": gates})
    data = {"names": NAMES, "models": MODELS,
            "manifests": {m: {k: v[k] for k in ("model_tag", "model_digest", "ollama_version", "gpu", "episodes_expected",
                                                "episodes_written", "errored_keys", "runs_by_origin", "code_hash")}
                          for m, v in manifests.items()},
            "tables": {n: json.loads(pd.read_csv(EV / f"{n}.csv").to_json(orient="records")) for n in TABLES},
            "episodes": episodes}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("window.DEMO = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{len(episodes)} episodes -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
