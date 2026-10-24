"""Bundle for notebooks/kaggle/02_remaining_kaggle.ipynb -> dist/p2-netops-kaggle.zip. Upload it as a Kaggle dataset.

Holds the same code as the Colab zip plus the finished runs the notebook resumes from, as prior/<model>/traces.jsonl:
the partial Qwen grid from Colab and the pilot-v3 runs reused for Llama and Mistral. Each record is tagged with
'reused_from' so the manifest can count runs per origin. Errored and cut-off lines are left out (they are rerun).
"""
import json
import sys
import zipfile

from make_colab_zip import ROOT, code_files

sys.path.insert(0, str(ROOT / "src"))
from netinject.evaluation.judge import read_records  # noqa: E402

OUT = ROOT / "dist" / "p2-netops-kaggle.zip"
TRACES = ROOT / "results" / "traces"
PRIOR = {  # model -> (finished runs, origin)
    "qwen25_7b": (TRACES / "qwen25_7b" / "traces.jsonl", "colab"),
    "llama31_8b": (TRACES / "pilot_v3" / "llama31_8b" / "traces.jsonl", "pilot_v3"),
    "mistral_7b": (TRACES / "pilot_v3" / "mistral_7b" / "traces.jsonl", "pilot_v3"),
}

if __name__ == "__main__":
    missing = [str(p.relative_to(ROOT)) for p, _ in PRIOR.values() if not p.exists()]
    if missing:
        sys.exit(f"Missing {missing}. Download MyDrive/p2-netops/results/traces/qwen25_7b/traces.jsonl "
                 "from Google Drive into results/traces/qwen25_7b/ first.")
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in code_files():
            z.write(p, p.relative_to(ROOT).as_posix())
        for model, (path, origin) in PRIOR.items():
            ok = [r for r in read_records(path) if r.get("error") is None]
            z.writestr(f"prior/{model}/traces.jsonl",
                       "".join(json.dumps({**r, "reused_from": r.get("reused_from", origin)}) + "\n" for r in ok))
            print(f"{model}: {len(ok)} finished runs from {origin}")
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")
