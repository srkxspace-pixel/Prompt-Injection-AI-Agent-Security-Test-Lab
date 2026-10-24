"""Runs the experiment grid for one model (used by the Colab notebooks).

Writes one JSON line per (episode, temperature, run) holding the traces of all three gates. Resumable: keys that
already have a successful line are skipped, so a disconnected Colab session just restarts the cell.
"""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from netinject.agent.loop import SYSTEM_PROMPT, run_episode
from netinject.evaluation.judge import read_records
from netinject.scenarios.compose import all_episodes, scenarios_hash

ROOT = Path(__file__).resolve().parents[2]


def load_configs() -> tuple[dict, dict]:
    grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
    models = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text(encoding="utf-8"))
    return grid, models


def code_hash() -> str:
    """Hash of the harness code (prompts, task wording, parser, gates live in code, not in configs)."""
    h = hashlib.sha256()
    for p in sorted((ROOT / "src" / "netinject").rglob("*.py")):
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def configs_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "configs").glob("*.yaml")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def plan(task_ids: list[str] | None, decoding: list[dict]) -> list[tuple]:
    """All (key, episode, temperature, run) jobs for the given tasks (None = all tasks)."""
    eps = [e for e in all_episodes() if task_ids is None or e.task_id in task_ids]
    return [(f"{ep.id}|t{d['temperature']}|r{r}", ep, d["temperature"], r)
            for ep in eps for d in decoding for r in range(d["runs"])]


def finished_keys(path: Path) -> set[str]:
    return {r["key"] for r in read_records(path) if r.get("error") is None} if path.exists() else set()


def run_grid(llm, model_key: str, out_path: Path, jobs: list[tuple], max_steps: int, parallel: int = 1,
             max_calls_per_turn: int | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = finished_keys(out_path)
    todo = [j for j in jobs if j[0] not in done]
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo)} already done, {len(todo)} to run")
    lock, counter, t0 = threading.Lock(), [0], time.time()

    def work(job):
        key, ep, temperature, run = job
        start, traces, error = time.time(), None, None
        for _ in range(2):  # one retry, e.g. after an Ollama timeout
            try:
                traces, error = run_episode(ep, llm, temperature, run, max_steps, max_calls_per_turn), None
                break
            except Exception as e:  # recorded, counted as errored, retried on the next resume
                error = repr(e)
        record = {"key": key, "episode_id": ep.id, "episode_hash": ep.hash, "model": model_key,
                  "temperature": temperature, "run": run, "seconds": round(time.time() - start, 2),
                  "traces": traces, "error": error}
        with lock:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            counter[0] += 1
            n = counter[0]
            if n % 10 == 0 or n == len(todo):
                rate = n / (time.time() - t0)
                print(f"{n}/{len(todo)} done, {rate * 3600:.0f} runs/h, ETA {(len(todo) - n) / rate / 60:.0f} min")

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(work, todo))


def write_manifest(out_dir: Path, run_id: str, model_key: str, tag: str, digest: str, ollama_version: str,
                   gpu: str, jobs: list[tuple], started: str, finished: str) -> dict:
    """ARCHITECTURE §6 manifest, written next to the traces."""
    records = list(read_records(out_dir / "traces.jsonl"))
    ok = {r["key"] for r in records if r.get("error") is None}
    errored = {r["key"] for r in records if r.get("error") is not None} - ok
    manifest = {"run_id": run_id, "model_key": model_key, "model_tag": tag, "model_digest": digest,
                "ollama_version": ollama_version, "gpu": gpu, "configs_hash": configs_hash(),
                "scenarios_hash": scenarios_hash(), "code_hash": code_hash(),
                "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "episodes_expected": len(jobs), "episodes_written": len(ok), "episodes_errored": len(errored),
                "errored_keys": sorted(errored), "started": started, "finished": finished}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
