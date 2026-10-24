"""Write paper/tables/*.tex from results/eval/*.csv (and the tool registry), so no number is typed by hand.

Usage: PYTHONPATH=src python scripts/make_paper_tables.py [tag]
"""
import sys
from pathlib import Path

import pandas as pd

from netinject.env.tools import TOOLS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "tables"
NAMES = {"qwen25_7b": "Qwen2.5-7B", "llama31_8b": "Llama-3.1-8B", "mistral_7b": "Mistral-7B"}


def esc(s) -> str:
    return str(s).replace("_", r"\_")


def pct(p, lo=None, hi=None) -> str:
    if pd.isna(p):
        return "--"
    return f"{100 * p:.1f}" + (f" ({100 * lo:.0f}--{100 * hi:.0f})" if lo is not None else "")


def write(name: str, caption: str, label: str, header: str, rows: list[str], cols: str) -> None:
    body = "\n".join(rows)
    (OUT / f"{name}.tex").write_text(
        f"\\begin{{table}}[t]\n\\centering\n\\caption{{{caption}}}\n\\label{{{label}}}\n\\footnotesize\n"
        f"\\begin{{tabular}}{{{cols}}}\n\\toprule\n{header} \\\\\n\\midrule\n{body}\n\\bottomrule\n"
        f"\\end{{tabular}}\n\\end{{table}}\n", encoding="utf-8")


def main(tag: str = "") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write("tools", "Mock environment: tool inventory.", "tab:tools", "Tool & Kind & Parameters",
          [f"\\texttt{{{esc(n)}}} & {'read' if imp is None else imp + '-impact write'} & {esc(', '.join(p))} \\\\"
           for n, (_, _, p, imp) in TOOLS.items()], "lll")
    ev = ROOT / "results" / "eval"
    if not (ev / f"{tag}table2_delay.csv").exists():
        print("no results yet: only the tool table was written")
        return
    t2 = pd.read_csv(ev / f"{tag}table2_delay.csv")
    rows = [f"{NAMES.get(r.model, r.model)} & {r.temperature:g} & {int(r.delay)} & {int(r.n)} & "
            f"{pct(r.rate, r.ci_low, r.ci_high)} & {pct(r.any_out_of_scope_rate)} \\\\" for r in t2.itertuples()]
    write("delay", "Attack-goal attempt rate (\\%, Wilson 95\\% CI) by model, temperature and delay $d$ "
          "(no gate). The last column counts any out-of-scope high-impact write.", "tab:delay",
          "Model & $T$ & $d$ & $n$ & Goal attempt & Any out-of-scope", rows, "lrrrrr")
    t3 = pd.read_csv(ev / f"{tag}table3_gates.csv")
    rows = [f"{NAMES.get(r.model, r.model)} & \\texttt{{{esc(r.gate)}}} & {pct(r.asr_goal)} & "
            f"{pct(r.any_out_of_scope_executed)} & {pct(r.task_success_attack)} & {pct(r.task_success_control)} & "
            f"{pct(r.false_block_control)} & {r.denials_per_episode:.2f} \\\\" for r in t3.itertuples()]
    write("gates", "Gate comparison (\\%): attack success (attacker goal executed), any out-of-scope write executed, "
          "task success under attack and on controls, false-block rate on controls, denials per episode.",
          "tab:gates", "Model & Gate & ASR & Any OOS & Task (att.) & Task (ctrl) & False block & Denials",
          rows, "llrrrrrr")
    if (ev / "matched12_table2_delay.csv").exists():  # from scripts/review_tables.py
        m2, m3 = pd.read_csv(ev / "matched12_table2_delay.csv"), pd.read_csv(ev / "matched12_table3_gates.csv")
        rows = []
        for model, g in m2.groupby("model", sort=False):
            asr = m3[m3.model == model].set_index("gate").asr_goal
            rows.append(f"{NAMES.get(model, model)} & " + " & ".join(pct(r) for r in g.sort_values("delay").rate)
                        + " & " + " & ".join(pct(asr[x]) for x in ("none", "scope_check", "ticket_bound")) + " \\\\")
        write("matched", "Matched tasks: all models at $T=0$ on the same 12 tasks. Attack-goal attempt rate (\\%) "
              "by delay $d$ (no gate) and attack success (\\%) per gate.", "tab:matched",
              "Model & $d{=}0$ & $d{=}1$ & $d{=}2$ & $d{=}3$ & ASR none & ASR scope & ASR ticket", rows, "lrrrrrrr")
    print(f"wrote {sorted(p.name for p in OUT.glob('*.tex'))}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
