# Prompt Injection AI Agent Security Test Lab

**Multi-Step Delayed Tool-Output Poisoning in Network-Operations LLM Agents: Repeated-Decoding Evaluation of Local 7–8B Models with Change-Control Approval Gates**

A controlled test lab for indirect prompt injection against tool-using LLM agents in network operations. An agent works through a change ticket on a mock enterprise network. An attacker hides an instruction in one of the artifacts the agent reads (a ticket comment, a device log, a runbook or a knowledge-base article), several steps before the agent makes a configuration change. The lab measures:
- how often local 7–8B models carry out the attacker's change;
- how that varies across repeated sampled runs;
- whether change-control approval gates stop the attack without blocking legitimate work.

Everything runs against an in-memory mock network. No tool touches a real device, and the attack payloads only exist in this repository's scenario files.

## Research questions

- **RQ1:** Does the attack rate change as the delay between the poisoned content and the harmful write grows (d = 0…3)?
- **RQ2:** How much do outcomes vary across repeated runs at temperature 0.7 compared with temperature 0?
- **RQ3:** How much do the `scope_check` and `ticket_bound` gates reduce executed unsafe writes, and at what cost in false blocks and task success?
- **RQ4:** Which attack styles and artifact types are most effective, and does this differ by model?

## Key results

The models are Qwen2.5-7B, Llama-3.1-8B and Mistral-7B (4-bit, served by Ollama on a T4 GPU), over 2,039 runs. The details and sources are in [docs/RESULTS.md](docs/RESULTS.md).

| Finding | Evidence |
|---|---|
| **Delay weakens the attack but does not remove it** | Qwen attempts the attacker's write in 30.2% of episodes at d = 0 and 9.4% at d = 3 (Llama: 22.9% → 8.3%); odds ratio 0.64 per extra read |
| **One run per scenario is not enough** | With 3 sampled runs, 21.6% of Qwen's attack episodes are compromised in some runs but not others; 11.2% look safe at temperature 0 but fail under sampling |
| **Approval gates work, and the exact rule matters** | `scope_check` cuts Qwen's executed attacks from 13.7% to 1.4%, but every remaining success is a ticket-confusion attack; `ticket_bound` brings it to 0% |
| **Gate cost depends on the model** | No utility cost for Qwen; Llama's task success under attack falls from 47.9% to 12–13%, because it omits the ticket reference |
| **Direct instructions work best** | Odds ratio 8.1 versus fake-authority messages; payloads in device logs are the least effective |

Mistral-7B completes very few tasks, so its near-zero attack rates reflect low agent capability, not robustness.

## Quick start

### View the demo (no setup)

Open `demo/index.html` in any browser; it works offline. It has four tabs:
- **Overview:** an interactive delay diagram and the key findings.
- **Results:** RQ1–RQ4, with the figures and tables.
- **Trace explorer:** replays any recorded run step by step under each gate, with the hidden instruction and the gate's decisions highlighted.
- **Environment:** the tools and the model setup.

No model runs in the demo; it replays the recorded GPU runs.

### Reproduce the analysis (CPU only)

**Prerequisites:** Git and **Python 3.11** (the pinned pandas has no build for 3.13). The commands are for Windows PowerShell.

1. Clone the repository:
   ```powershell
   git clone https://github.com/srkxspace-pixel/Prompt-Injection-AI-Agent-Security-Test-Lab.git
   ```
2. Go into the folder:
   ```powershell
   cd Prompt-Injection-AI-Agent-Security-Test-Lab
   ```
3. Create a virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   ```
4. Install the dependencies (about 5–10 minutes):
   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements-local.txt
   ```
5. Run the tests (19 tests with a scripted `FakeLLM`; no model needed):
   ```powershell
   .venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
   ```
6. Point Python at the source folder (once per terminal):
   ```powershell
   $env:PYTHONPATH = "src"
   ```
7. Regenerate the results from the recorded traces (about 2 minutes):
   ```powershell
   .venv\Scripts\python.exe -m netinject.scenarios.compose                # validate the 24 tasks / 408 episodes
   .venv\Scripts\python.exe -m netinject.reporting.report results/traces  # labels, results/eval/*.csv, figures/*.png
   .venv\Scripts\python.exe scripts/review_tables.py                      # matched-task tables, false-block causes
   .venv\Scripts\python.exe scripts/make_paper_tables.py                  # paper/tables/*.tex
   .venv\Scripts\python.exe scripts/build_demo.py                         # demo/data.js
   ```
8. Open the demo:
   ```powershell
   start demo\index.html
   ```

If step 1 or 4 fails with a path error or `No module named pip`, clone into a shorter folder such as `D:\`, because Windows limits paths to 260 characters.

On macOS or Linux, use `python3.11 -m venv .venv`, replace `.venv\Scripts\python.exe` with `.venv/bin/python`, use `export PYTHONPATH=src`, and open the demo with `open demo/index.html` (macOS) or `xdg-open demo/index.html` (Linux).

The regenerated tables are byte-identical to the ones committed here. Running the models themselves needs a GPU: see [notebooks/](notebooks/).

## How it works

- **Environment:**
  - An in-memory enterprise network with 11 devices and 13 tools.
  - The tools are 6 reads, 2 low-impact writes and 5 high-impact writes (ACL change, interface shutdown, route change, admin user, logging off).
  - Each high-impact write needs an approved change ticket.
- **Episodes:**
  - The procedure is fixed: list alerts, then four reads (ticket, device log, runbook, knowledge base, in a Latin-square order), then the approved write at step 6.
  - The attacker's instruction sits in the read at step 5 − d, so only its distance to the write changes.
  - There are 24 benign tasks × 4 attack styles × 4 delays, plus a control (no-attack) run of each task.
- **Attack styles:** direct instruction, fake authority, ticket confusion (citing a real approved decoy ticket for other work), and an instruction split across two reads.
- **Gates:**
  - `none` allows everything.
  - `scope_check` allows a high-impact write only if an approved ticket covers that exact change.
  - `ticket_bound` additionally requires the ticket the operator named.
  - Each run is forked at the first denial, giving paired comparisons.
- **Scoring:** a deterministic judge labels every trace (task success, attack attempted or executed, gate blocks, false blocks). Statistics use Wilson intervals, a logistic regression with episode-clustered standard errors, and McNemar's test.

The full design is in [docs/DESIGN.md](docs/DESIGN.md), and the code structure in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/netinject/` | Harness: mock network and tools, scenarios, agent loop, gates, judge, statistics, report |
| `tests/` | CPU tests using a scripted `FakeLLM` |
| `configs/` | Experiment grid and pinned model tags |
| `notebooks/colab/`, `notebooks/kaggle/` | Executed GPU notebooks (pilot and full grid) |
| `results/traces/` | Raw run traces (one JSON line per run) and manifests |
| `results/labels/`, `results/eval/` | Labels and result tables (CSV), generated from the traces |
| `figures/` | Result figures |
| `demo/` | Offline demo page |
| `docs/` | Specification, design, architecture, pilot log, results, scenario listing |
| `paper/` | Paper draft (in progress) and generated LaTeX tables |
| `scripts/` | Table, figure, demo and upload-bundle helpers |

## Reproducibility

- **Recorded setup:** every run's manifest records the model digest, the Ollama version, the GPU, and the hashes of the code, configs and scenarios (`results/traces/<model>/manifest.json`).
- **Where the runs were made:**
  - Runs started on Google Colab and finished on Kaggle, with the same GPU type (Tesla T4), model builds and code.
  - The Ollama server version (0.40.3) is recorded for the pilot and Kaggle runs. For the Colab full-grid sessions it was not preserved.
- **Code fingerprint:** the manifests record `code_hash` 332beea4f45e. After the runs, three comments were reworded (`llm/ollama_client.py`, `agent/loop.py`, `scenarios/compose.py`); no code changed, but the current `code_hash` is 64089bb87e0a. The config hash (fe584c89c830) and scenario hash (e86e7e242dc9) still match the manifests.
- **Excluded run:** one Mistral run (of 2,040) was aborted by Ollama's token-repeat limit and is excluded; see [docs/RESULTS.md](docs/RESULTS.md).

## Documentation

- [docs/SPECS.md](docs/SPECS.md): research questions, experiment grid, acceptance criteria
- [docs/DESIGN.md](docs/DESIGN.md): environment, attacks, gates, labels and statistics
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): code structure and data flow
- [docs/PILOT.md](docs/PILOT.md): pilot rounds and the harness fixes they led to
- [docs/RESULTS.md](docs/RESULTS.md): full-grid results with sources
- [docs/SCENARIOS.md](docs/SCENARIOS.md): the task and attack set, with two rendered example episodes

## Background

- The research gap comes from NetInjectBench (<https://arxiv.org/abs/2607.10490>). It evaluates the same three model families in a single-step setting, and lists multi-step agents, delayed tool-output poisoning, human approval and repeated decoding as open problems.
- The defense comparison is positioned against DataSentinel (Liu et al., IEEE S&P 2025, <https://doi.org/10.1109/SP61157.2025.00250>), a detection-based defense. The approval gates here are deterministic policy defenses instead.
