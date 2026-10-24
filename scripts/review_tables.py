"""Extra result tables, written to results/eval/:
- matched12_table2_delay.csv, matched12_table3_gates.csv: every model at T=0 on the 12 tasks that Llama and
  Mistral ran (configs/grid.yaml tasks_overrides), so cross-model comparisons use the same tasks.
- false_block_causes.csv: for each gate branch with a false block, whether the first denied (legitimate) write
  lacked ticket_id, and whether the agent later re-issued that write in an allowed form.

Usage: PYTHONPATH=src python scripts/review_tables.py
Kept in scripts/ so src/netinject (and the code_hash recorded with the model runs) stays unchanged.
"""
import pandas as pd

from netinject.evaluation.judge import read_records
from netinject.reporting.report import ROOT, load_labels, tables
from netinject.run import load_configs


def false_block_causes(df: pd.DataFrame, traces_dir) -> pd.DataFrame:
    fb = df[(df.gate != "none") & df.false_block]
    keys = set(zip(fb.model, fb.episode_id, fb.temperature, fb.run, fb.gate))
    rows = []
    for model in sorted(fb.model.unique()):
        for r in read_records(traces_dir / model / "traces.jsonl"):
            if r.get("error") is not None:
                continue
            for gate in ("scope_check", "ticket_bound"):
                if (model, r["episode_id"], r["temperature"], r["run"], gate) not in keys:
                    continue
                tools = [e for e in r["traces"][gate]["events"] if e["type"] == "tool"]
                first = next(i for i, e in enumerate(tools) if not e["allowed"])
                rows.append({"model": model, "gate": gate, "missing_ticket_id": "ticket_id" not in tools[first]["args"],
                             "retried_allowed": any(e["name"] == tools[first]["name"] and e["allowed"]
                                                    for e in tools[first + 1:])})
    return (pd.DataFrame(rows).groupby(["model", "gate"])
            .agg(false_block_branches=("missing_ticket_id", "size"), missing_ticket_id=("missing_ticket_id", "sum"),
                 retried_allowed=("retried_allowed", "sum")).reset_index())


if __name__ == "__main__":
    grid, _ = load_configs()
    subset = grid["tasks_overrides"]["llama31_8b"]
    assert subset == grid["tasks_overrides"]["mistral_7b"]
    traces, ev = ROOT / "results" / "traces", ROOT / "results" / "eval"
    df = load_labels(traces)
    t = tables(df[df.task_id.isin(subset) & (df.temperature == 0)])
    for name in ("table2_delay", "table3_gates"):
        t[name].to_csv(ev / f"matched12_{name}.csv", index=False)
    causes = false_block_causes(df, traces)
    causes.to_csv(ev / "false_block_causes.csv", index=False)
    print(causes.to_string(index=False))
    print("-> results/eval/matched12_*.csv, false_block_causes.csv")
