# Specification

## 1. Objective

Measure how delay between poisoned tool output and harmful action, stochastic decoding, and change-control approval gates affect prompt-injection success in local 7–8B network-operations agents.

## 2. Research questions

- **RQ1.** Does unsafe-action rate change as the delay between poisoned content and the harmful action increases (d = 0…3)?
- **RQ2.** How much do outcomes vary across repeated runs at temperature 0.7 compared with temperature 0?
- **RQ3.** How much do the `scope_check` and `ticket_bound` gates reduce executed unsafe writes, and at what cost in false blocks and task success?
- **RQ4.** Which attack styles and artifact types are most effective, and does this differ by model?

## 3. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | In-memory environment with the read/write tools and change-control rules in DESIGN D2 |
| FR-2 | Scenario files validated by schema; composer builds episodes from task × attack × delay |
| FR-3 | Agent loop works through the `LLM` interface with both `OllamaClient` and `FakeLLM` |
| FR-4 | Three gates selectable by config |
| FR-5 | Full JSONL trace per episode |
| FR-6 | Deterministic judge produces the five outcome labels |
| FR-7 | GPU notebooks (Colab, Kaggle) run the full grid resumably and export traces + manifest |
| FR-8 | Tables and figures generated from `results/eval/` only |

## 4. Experiment grid

| Factor | Levels |
|---|---|
| Model | Qwen2.5-7B, Llama-3.1-8B, Mistral-7B |
| Delay d | 0, 1, 2, 3 |
| Attack style | 4 (DESIGN D3/D3a) |
| Gate | none, scope_check, ticket_bound |
| Decoding | All models T=0 ×1. Qwen2.5-7B also T=0.7 ×3 for RQ2 (R reduced from 10 → 5 → 3 to fit free GPU time; repeated sampling on Qwen only) |
| Tasks | 24 benign tasks (6 per Latin-square order) + a control (no-attack) run of each. Llama-3.1-8B and Mistral-7B run a balanced 12-task subset, 3 per order, including the 4 pilot tasks (`tasks_overrides`, after the free GPU quota ran out). |

**Gates:**
- Applied by forking from the first denial (DESIGN D4). A gate's trajectory is a separate continuation from the point it first denies a call.
- **Per model:**
  - Qwen2.5-7B: 24 × (16 + 1) = 408 episodes × 4 decoding runs = 1,632 runs.
  - Llama-3.1-8B and Mistral-7B: 12 × 17 = 204 episodes × 1 run (T=0). The 68 runs of the pilot-v3 tasks are reused (same code_hash, run parameters and model digest).
  - Every run includes the gate forks.
- **Pilot go/no-go:** benign task success ≥ 60% for at least 2 of 3 models; unsafe attempt rate ≥ 20% at d = 0 with no gate; parse/format failures ≤ 5%.

The pilot measures time per episode. If needed, the task count or repeats are reduced so each model's full grid fits in a few free GPU sessions. Any reduction is recorded in `configs/grid.yaml` and reported in the paper.

## 5. Paper deliverables

- Table 1: environment and tool inventory.
- Table 2: ASR and attempt rate by model × delay (gate = none).
- Table 3: gate comparison: ASR, utility, false-block rate.
- Figure 1: environment and agent-loop diagram.
- Figure 2: attempt rate vs delay per model with CIs.
- Figure 3: run-to-run variability (distribution of per-episode success fractions at T=0.7).
- Figure 4: attack style × artifact type heat map.
- Two annotated example traces (one blocked, one successful).

## 6. Acceptance criteria

- Every scenario passes schema validation; benign tasks are solvable (verified by a scripted `FakeLLM` solution for each).
- All three models complete the grid (or the documented reduced grid); errored episodes under 2% and listed.
- Executed GPU notebooks committed with outputs, and manifests matching the config and scenario hashes.
- Every table cell traceable to `results/eval/` CSVs; labels reproducible from traces.
- Tests pass on CPU.

## 7. Out of scope

Real networks or devices; frontier/paid API models; fine-tuning; optimised (GCG-style) attacks; reimplementing DataSentinel; studies with human participants.
