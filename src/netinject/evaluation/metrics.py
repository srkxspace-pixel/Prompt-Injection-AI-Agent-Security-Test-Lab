"""Rates with Wilson 95% confidence intervals (DESIGN D7)."""
import math

import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Proportion k/n with its Wilson score interval."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, centre - half, centre + half


def rate_table(df: pd.DataFrame, by: list[str], col: str) -> pd.DataFrame:
    """Rate of boolean column `col` per group, with n and Wilson CI."""
    rows = []
    for key, g in df.groupby(by, dropna=False):
        k, n = int(g[col].sum()), len(g)
        p, lo, hi = wilson(k, n)
        rows.append({**dict(zip(by, key if isinstance(key, tuple) else (key,))), "n": n, "k": k,
                     "rate": p, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)
