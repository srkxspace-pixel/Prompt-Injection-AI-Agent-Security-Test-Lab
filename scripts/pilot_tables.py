"""Write results/labels/pilot_v*_labels.csv and results/eval/pilot_v*_*.csv, the source of the pilot numbers in docs/PILOT.md and
the paper's pilot section.

Usage: PYTHONPATH=src python scripts/pilot_tables.py
v2 was recorded before the step-6 wording change, so its scenario hashes are not checked (see judge.label_file).
"""
import pandas as pd

from netinject.evaluation.judge import label_file
from netinject.reporting.report import ROOT, tables

for version, check_hash in (("v2", False), ("v3", True)):
    files = sorted((ROOT / "results" / "traces" / f"pilot_{version}").glob("*/traces.jsonl"))
    df = pd.concat([label_file(f, check_hash) for f in files], ignore_index=True)
    df.to_csv(ROOT / "results" / "labels" / f"pilot_{version}_labels.csv", index=False)
    t = tables(df)
    for name, table in t.items():
        table.to_csv(ROOT / "results" / "eval" / f"pilot_{version}_{name}.csv", index=False)
    print(f"pilot_{version}: {len(files)} models -> results/eval/pilot_{version}_*.csv")
