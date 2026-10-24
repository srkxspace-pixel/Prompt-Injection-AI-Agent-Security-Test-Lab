# Architecture

## 1. Folder structure

```
.
├── README.md
├── requirements-local.txt        # CPU harness: pydantic, pyyaml, numpy, pandas, scipy, statsmodels, matplotlib, pytest
├── requirements-colab.txt        # GPU notebooks: ollama (python client) + harness deps
├── configs/
│   ├── models.yaml               # pinned Ollama tags + digest prefixes
│   └── grid.yaml                 # decoding × repeats, max steps, context, parallelism, task subsets, pilot slice
│                                 # (gate rules are code: gate/gates.py)
├── src/netinject/
│   ├── env/                      # state.py (in-memory network), tools.py (13 tools), change_control.py
│   ├── scenarios/
│   │   ├── schema.py             # pydantic models for tasks and attacks
│   │   ├── compose.py            # benign task + attack + delay -> runnable episode; validate()
│   │   └── data/                 # world.yaml, tasks/T01-T24.yaml, attacks/{goals,styles}.yaml
│   ├── agent/loop.py             # system prompt, tool-calling loop, gate forking
│   ├── llm/                      # base.py (AssistantTurn), ollama_client.py (+ text-call parser), fake_llm.py
│   ├── gate/gates.py             # none, scope_check, ticket_bound
│   ├── evaluation/               # judge.py (deterministic labels), metrics.py (Wilson CI), stats.py (logit, McNemar)
│   ├── reporting/report.py       # CSV tables + figures from results/traces (python -m netinject.reporting.report)
│   └── run.py                    # resumable grid runner + manifest (called by the notebooks)
├── notebooks/
│   ├── colab/                    # executed pilot notebooks (v1-v3) and the Qwen full-grid notebook
│   └── kaggle/                   # executed notebook that finished the full grid
├── results/
│   ├── traces/<model>/traces.jsonl         # one line per (episode, temperature, run), holding all 3 gate branches
│   │                                       # pilot rounds in traces/pilot*/<model>/
│   ├── labels/                             # outcome labels computed from the traces
│   └── eval/                               # metric tables (CSV)
├── figures/                      # result figures (PNG)
├── demo/                         # offline demo page (index.html + data.js)
├── scripts/  tests/  paper/
└── docs/
```

## 2. Runtime flow of one episode

```
scenario (task + attack + delay d) ──► env.reset(state)
         │
         ▼
  agent loop (max N steps)
    ├─ LLM proposes tool call
    ├─ read tool?  → returns artifact; poisoned artifact injected at step k
    ├─ write tool? → approval gate decides allow / deny
    │                 allow → env state changes; deny → refusal returned to agent
    └─ stop when agent finishes or N reached
         │
         ▼
  trace.jsonl  ──►  judge (deterministic, from final state + trace)
                     labels: task_success, unsafe_write_attempted,
                             unsafe_write_executed, gate_blocked, false_block
```

"Delay" `d` is the number of agent steps between the step that delivers the poisoned content and the earliest step at which the harmful write becomes possible. `d = 0` reproduces the single-step setting.

## 3. Interfaces

- `LLM.chat(messages, tools, temperature, seed) -> AssistantTurn`: implemented by `OllamaClient` (GPU notebooks) and `FakeLLM` (local tests). The agent code depends only on this interface.
- `Tool`: name, JSON schema, `call(state, args) -> str`, `is_write: bool`, `impact: low|high`.
- `Gate.review(proposed_call, state, history) -> Decision(allow, reason)`.

## 4. CPU and GPU boundary

| Local CPU | GPU notebook (Colab or Kaggle) |
|---|---|
| Environment, scenarios, validator | Ollama server and model pulls |
| Agent loop, tested with `FakeLLM` | Running every episode with the real models |
| Judge, metrics, statistics, figures | Writing traces |

The boundary is `results/traces/`. The notebooks produce traces only; labels and metrics are computed locally from the traces, so scoring can be fixed or audited without re-running any model.

## 5. Notebook contract

Each notebook has:
1. **Header cell:** purpose, model, grid slice, expected runtime on a free T4, date.
2. **Setup cell:** get the code; install Ollama; start the server; `ollama pull <tag>`; record the model digest; print GPU and versions.
3. **Config cell:** load `configs/*.yaml`; no hard-coded parameters.
4. **Resumable loop:** skip episodes whose trace already exists, so a disconnected session restarts cleanly. Traces are saved after every episode.
5. **Outputs:** `results/traces/<model>/traces.jsonl` and `manifest.json`, zipped for download.
6. **Final cell:** completeness check (episodes expected vs written, error count).

The executed notebook is stored in `notebooks/`, and its traces are unzipped into `results/traces/`.

## 6. Manifest

```json
{
  "run_id": "02_qwen25_7b_kaggle_2026-10-20",
  "model_tag": "<ollama tag>", "model_digest": "<sha>",
  "ollama_version": "<version>", "gpu": "Tesla T4",
  "configs_hash": "<sha256>", "scenarios_hash": "<sha256>", "code_hash": "<sha256>",
  "episodes_expected": 0, "episodes_written": 0, "episodes_errored": 0, "errored_keys": [],
  "started": "...", "finished": "...", "runs_by_origin": {"colab": 0, "kaggle": 0}
}
```
