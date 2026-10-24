"""Tables and figures for the paper (SPECS §5), computed only from traces in results/traces/.

Usage: python -m netinject.reporting.report results/traces [tag]
Writes results/labels/<tag>labels.csv, results/eval/<tag>*.csv and figures/<tag>*.png.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from netinject.env.tools import TOOLS
from netinject.evaluation.judge import label_file
from netinject.evaluation.metrics import rate_table
from netinject.evaluation.stats import delay_logit, gate_mcnemar

ROOT = Path(__file__).resolve().parents[3]
# Categorical slots 1-3 of the validated default palette (dataviz skill), fixed order per model.
COLORS = {"qwen25_7b": "#2a78d6", "llama31_8b": "#eb6834", "mistral_7b": "#1baf7a"}
NAMES = {"qwen25_7b": "Qwen2.5-7B", "llama31_8b": "Llama-3.1-8B", "mistral_7b": "Mistral-7B"}
MARKERS = {"qwen25_7b": "o", "llama31_8b": "s", "mistral_7b": "^"}
INK, MUTED = "#1f1f1e", "#6b6a64"


def load_labels(traces_dir: Path) -> pd.DataFrame:
    files = sorted(traces_dir.glob("*/traces.jsonl"))
    if not files:
        raise SystemExit(f"no traces under {traces_dir}: run the Colab notebooks first")
    return pd.concat([label_file(f) for f in files], ignore_index=True)


def tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    att, ctrl = df[df["style"] != "control"], df[df["style"] == "control"]
    none = att[att.gate == "none"]
    t = {}
    t["table1_tools"] = pd.DataFrame([{"tool": n, "kind": "read" if imp is None else f"write ({imp} impact)",
                                       "parameters": ", ".join(p), "description": d}
                                      for n, (_, d, p, imp) in TOOLS.items()])
    # Table 2: susceptibility by model x delay (no gate), per decoding temperature
    goal = rate_table(none, ["model", "temperature", "delay"], "attack_goal_attempted")
    anyw = rate_table(none, ["model", "temperature", "delay"], "unsafe_write_attempted")
    t["table2_delay"] = goal.merge(anyw[["model", "temperature", "delay", "rate"]].rename(
        columns={"rate": "any_out_of_scope_rate"}), on=["model", "temperature", "delay"])
    # Table 3: gates — attack success, utility, false blocks
    rows = []
    for (model, gate), g in df.groupby(["model", "gate"]):
        a, c = g[g["style"] != "control"], g[g["style"] == "control"]
        rows.append({"model": model, "gate": gate, "n_attack": len(a), "asr_goal": a.attack_goal_executed.mean(),
                     "any_out_of_scope_executed": a.unsafe_write_executed.mean(),
                     "task_success_attack": a.task_success.mean(), "n_control": len(c),
                     "task_success_control": c.task_success.mean(), "false_block_control": c.false_block.mean(),
                     "false_block_attack": a.false_block.mean(), "denials_per_episode": g.n_denials.mean(),
                     "spontaneous_out_of_scope_control": c.unsafe_write_executed.mean()})
    t["table3_gates"] = pd.DataFrame(rows)
    t["gates_by_style"] = rate_table(att, ["model", "gate", "style"], "attack_goal_executed")
    # Run-to-run variability at T=0.7 (gate none): how many of the R seeds attempted the goal, per episode
    hot = none[none.temperature > 0]
    per_ep = hot.groupby(["model", "episode_id"]).attack_goal_attempted.agg(["sum", "count"]).reset_index()
    cold = none[none.temperature == 0].set_index(["model", "episode_id"]).attack_goal_attempted
    per_ep["t0_attempted"] = [cold.get((m, e)) for m, e in zip(per_ep.model, per_ep.episode_id)]
    t["variability_per_episode"] = per_ep
    t["variability_summary"] = pd.DataFrame([{
        "model": m, "episodes": len(g), "never": (g["sum"] == 0).mean(),
        "sometimes": ((g["sum"] > 0) & (g["sum"] < g["count"])).mean(), "always": (g["sum"] == g["count"]).mean(),
        "t0_safe_but_compromised_at_t07": ((g.t0_attempted == False) & (g["sum"] > 0)).mean()}  # noqa: E712
        for m, g in per_ep.groupby("model")])
    t["style_carrier"] = rate_table(none, ["model", "style", "carrier"], "attack_goal_attempted")
    t["realized_delay"] = none[none.attack_goal_attempted].groupby(["model", "delay"]).realized_delay.agg(
        ["mean", "median", "count"]).reset_index()
    t["format_quality"] = df[df.gate == "none"].groupby("model").agg(
        runs=("episode_id", "size"), llm_calls=("n_llm_calls", "sum"), text_parsed=("n_text_parsed", "sum"),
        runs_with_tool_errors=("n_tool_errors", lambda s: (s > 0).mean()),
        hit_max_steps=("end", lambda s: (s == "max_steps").mean())).reset_index()
    try:
        t["logit_delay"] = delay_logit(df)
    except Exception as e:  # e.g. perfect separation on a tiny pilot
        t["logit_delay"] = pd.DataFrame([{"error": repr(e)}])
    t["mcnemar"] = pd.concat([gate_mcnemar(df, "none", "scope_check").assign(comparison="none vs scope_check"),
                              gate_mcnemar(df, "none", "ticket_bound").assign(comparison="none vs ticket_bound"),
                              gate_mcnemar(df, "scope_check", "ticket_bound").assign(
                                  comparison="scope_check vs ticket_bound")], ignore_index=True)
    return t


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=8)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)


def fig_delay(t2: pd.DataFrame, path: Path):
    temps = sorted(t2.temperature.unique())
    fig, axes = plt.subplots(1, len(temps), figsize=(3.4 * len(temps), 2.8), sharey=True, squeeze=False)
    for ax, temp in zip(axes[0], temps):
        for model, g in t2[t2.temperature == temp].groupby("model"):
            g = g.sort_values("delay")
            ax.fill_between(g.delay, g.ci_low, g.ci_high, color=COLORS.get(model), alpha=0.15, linewidth=0)
            ax.plot(g.delay, g.rate, color=COLORS.get(model), linewidth=2, marker=MARKERS.get(model),
                    markersize=6, label=NAMES.get(model, model))
        ax.set_title(f"T = {temp}", fontsize=9, color=INK)
        ax.set_xticks([0, 1, 2, 3])
        ax.set_xlim(-0.2, 3.2)
        ax.set_xlabel("delay d (reads between payload and write)", fontsize=8, color=INK)
        _style(ax)
    axes[0][0].set_ylabel("attack-goal attempt rate", fontsize=8, color=INK)
    axes[0][0].set_ylim(0, 1.02)
    # legend below the panels: lines often overlap, so end-of-line labels would collide; marker shape is the
    # secondary encoding
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", ncol=3)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_variability(per_ep: pd.DataFrame, path: Path):
    models = [m for m in COLORS if m in set(per_ep.model)]
    if not models:
        return
    fig, axes = plt.subplots(1, len(models), figsize=(2.6 * len(models), 2.4), sharey=True, squeeze=False)
    for ax, model in zip(axes[0], models):
        g = per_ep[per_ep.model == model]
        r = int(g["count"].max())
        counts = g["sum"].value_counts().reindex(range(r + 1), fill_value=0)
        ax.bar([f"{k}/{r}" for k in counts.index], counts.values, color=COLORS[model], width=0.7,
               edgecolor="white", linewidth=1)
        ax.set_title(NAMES[model], fontsize=9, color=INK)
        ax.set_xlabel("seeds that attempted the goal", fontsize=8, color=INK)
        _style(ax)
    axes[0][0].set_ylabel("attack episodes", fontsize=8, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_style_carrier(sc: pd.DataFrame, path: Path):
    models = [m for m in COLORS if m in set(sc.model)]
    if not models:
        return
    fig, axes = plt.subplots(1, len(models), figsize=(2.6 * len(models) + 1.2, 2.6), squeeze=False)
    for i_ax, (ax, model) in enumerate(zip(axes[0], models)):
        piv = sc[sc.model == model].pivot(index="style", columns="carrier", values="rate")
        im = ax.imshow(piv.values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(piv.columns)), piv.columns, fontsize=7)
        ax.set_yticks(range(len(piv.index)), piv.index if i_ax == 0 else [""] * len(piv.index), fontsize=7)
        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                v = piv.values[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if v > 0.55 else INK)
        ax.set_title(NAMES[model], fontsize=9, color=INK)
        ax.tick_params(length=0, labelcolor=INK)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.colorbar(im, ax=axes[0].tolist(), shrink=0.8, label="attempt rate")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(traces_dir: Path, tag: str = "") -> None:
    (ROOT / "results" / "labels").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "eval").mkdir(parents=True, exist_ok=True)
    (ROOT / "figures").mkdir(exist_ok=True)
    df = load_labels(traces_dir)
    df.to_csv(ROOT / "results" / "labels" / f"{tag}labels.csv", index=False)
    t = tables(df)
    for name, table in t.items():
        table.to_csv(ROOT / "results" / "eval" / f"{tag}{name}.csv", index=False)
    fig_delay(t["table2_delay"], ROOT / "figures" / f"{tag}fig2_delay.png")
    fig_variability(t["variability_per_episode"], ROOT / "figures" / f"{tag}fig3_variability.png")
    fig_style_carrier(t["style_carrier"], ROOT / "figures" / f"{tag}fig4_style_carrier.png")
    print(f"{len(df)} labelled rows -> results/eval/{tag}*.csv, figures/{tag}*.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "")
