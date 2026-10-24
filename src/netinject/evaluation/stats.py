"""Statistical tests (DESIGN D7): logistic regression with episode-clustered SEs, paired McNemar for gates."""
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar


def delay_logit(df: pd.DataFrame, outcome: str = "attack_goal_attempted") -> pd.DataFrame:
    """Logit of `outcome` on delay (linear), model, style and carrier artifact; gate 'none' attack runs only.
    Standard errors are clustered by episode because the R seeds of one episode are repeated measures."""
    d = df[(df.gate == "none") & (df["style"] != "control")].copy()
    d["y"] = d[outcome].astype(int)
    fit = smf.glm("y ~ delay + C(model) + C(style) + C(carrier)", data=d, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["model"] + d["episode_id"])[0]})
    ci = fit.conf_int()
    return pd.DataFrame({"coef": fit.params, "se": fit.bse, "p": fit.pvalues,
                         "ci_low": ci[0], "ci_high": ci[1]}).reset_index(names="term")


def gate_mcnemar(df: pd.DataFrame, gate_a: str, gate_b: str, outcome: str = "attack_goal_executed",
                 by: str = "model") -> pd.DataFrame:
    """Paired comparison of two gates on the same (episode, temperature, run) — they share a forked prefix."""
    rows = []
    for key, g in df[df["style"] != "control"].groupby(by):
        wide = g.pivot_table(index=["episode_id", "temperature", "run"], columns="gate", values=outcome,
                             aggfunc="first").dropna(subset=[gate_a, gate_b])
        a, b = wide[gate_a].astype(bool), wide[gate_b].astype(bool)
        table = [[int((a & b).sum()), int((a & ~b).sum())], [int((~a & b).sum()), int((~a & ~b).sum())]]
        res = mcnemar(table, exact=True)
        rows.append({by: key, "n_pairs": len(wide), f"{gate_a}_rate": a.mean(), f"{gate_b}_rate": b.mean(),
                     "only_a": table[0][1], "only_b": table[1][0], "p": res.pvalue})
    return pd.DataFrame(rows)
