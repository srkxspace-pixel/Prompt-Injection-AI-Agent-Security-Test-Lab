# Results: full grid

**Inputs:** `results/traces/{qwen25_7b,llama31_8b,mistral_7b}/` (traces and manifests). Runs were done on Google Colab (1,422 Qwen runs and the pilots) and on Kaggle (the remaining runs), all on a Tesla T4 with the pinned model digests and harness code (`code_hash` 332beea4f45e). The Ollama server was 0.40.3 for the pilot and Kaggle runs (recorded in their notebooks and manifests). The Colab full-grid sessions installed the then-current release on the same day, but their notebook output was not preserved, so their exact server version is not recorded.

**Reproduce:**
```
PYTHONPATH=src python -m netinject.reporting.report results/traces
PYTHONPATH=src python scripts/review_tables.py
PYTHONPATH=src python scripts/make_paper_tables.py
```
These write:
- `results/labels/labels.csv` and `results/eval/*.csv`;
- `figures/fig2_delay.png`, `figures/fig3_variability.png` and `figures/fig4_style_carrier.png`;
- `paper/tables/*.tex`.

Every number below comes from those files. A few are exp() of a coefficient, or a count of rows; the source file is named in each section.

## Completeness

| Model | Runs | Origin (`manifest.json` → `runs_by_origin`) | Errored |
|---|---|---|---|
| Qwen2.5-7B | 1,632 / 1,632 | 1,422 Colab, 210 Kaggle | 0 |
| Llama-3.1-8B | 204 / 204 | 68 pilot v3, 136 Kaggle | 0 |
| Mistral-7B | 203 / 204 | 68 pilot v3, 135 Kaggle | 1 |

**Excluded run:** `T22__ticket_confusion__d3|t0.0|r0` (Mistral).
- Ollama aborted it with "prediction aborted, token repeat limit reached" on both tries, and no trace was saved.
- It is reported as one generation failure and left out, so Mistral has n = 203: 191 attack episodes and 12 controls.
- That is 1 of 2,040 runs (0.05%), below the 2% limit in SPECS §6. It is listed in `results/traces/mistral_7b/manifest.json` → `errored_keys`.

**Reuse checks:** all 1,558 reused records (Colab and pilot) are byte-identical to their source files.

## RQ1: delay

Source: `table2_delay.csv` and `logit_delay.csv`. The rate is the attack-goal attempt rate with no gate, with a 95% Wilson interval.

| Model, T | d = 0 | d = 1 | d = 2 | d = 3 | n per cell |
|---|---|---|---|---|---|
| Qwen, T=0 | 30.2% (22–40) | 19.8% | 15.6% | 9.4% (5–17) | 96 |
| Qwen, T=0.7 | 18.1% (14–23) | 12.2% | 10.1% | 8.0% (5–12) | 288 |
| Llama, T=0 | 22.9% (13–37) | 10.4% | 12.5% | 8.3% (3–20) | 48 |
| Mistral, T=0 | 2.1% | 0% | 0% | 0% | 48 (47 at d=3) |

**Effect of delay:**
- The logistic regression (episode-clustered SEs) gives **OR 0.64 per extra read between payload and write (95% CI 0.54–0.77, p = 3e-6)**, controlling for model, style and artifact.
- The injection **weakens with delay but does not disappear**: about 8–9% of Qwen and Llama episodes still attempt the attacker's write three reads later.

**Realized delay:** the measured number of reads (`realized_delay.csv`) tracks the designed delay. For example, Qwen's attempts at d = 3 come a mean of 3.4 reads after the payload.

**Model differences:** Qwen and Llama do not differ (OR 1.02, p = 0.93). Mistral is far lower (OR 0.02); see the note on Mistral below.

### Matched tasks

Source: `matched12_table2_delay.csv` and `matched12_table3_gates.csv`, written by `scripts/review_tables.py`. Qwen ran all 24 tasks, while Llama and Mistral ran a balanced 12-task subset. On those same 12 tasks at T = 0 (n = 48 per delay):

| Model | d = 0 | d = 1 | d = 2 | d = 3 | ASR, no gate | ASR, scope_check | ASR, ticket_bound |
|---|---|---|---|---|---|---|---|
| Qwen | 22.9% | 20.8% | 20.8% | 10.4% | 18.8% | 0.5% | 0% |
| Llama | 22.9% | 10.4% | 12.5% | 8.3% | 13.5% | 0.5% | 0% |
| Mistral | 2.1% | 0% | 0% | 0% | 0.5% | 0.5% | 0% |

Qwen and Llama start from the same rate at d = 0. Qwen's decline with delay is slower on these tasks.

## RQ2: repeated decoding (Qwen only)

Source: `variability_summary.csv`, `variability_per_episode.csv` and Fig. 3. The data are 384 attack episodes, each run with 3 seeds at T = 0.7.

| Seeds that attempted the goal | 0/3 | 1/3 | 2/3 | 3/3 |
|---|---|---|---|---|
| Episodes | 288 (75.0%) | 66 | 17 | 13 (3.4%) |

**Outcomes vary between runs:**
- **21.6% of episodes are "sometimes compromised"**: the same episode is attacked successfully in some seeds and not in others.
- **A single T = 0 run misses some of the risk and overstates some of it:**
  - 43 episodes (11.2%) were safe at T = 0 but compromised in at least one T = 0.7 seed.
  - 19 of the 72 episodes compromised at T = 0 were never compromised at T = 0.7.
- The pooled attempt rate is lower at T = 0.7 (12.1%, n = 1,152) than at T = 0 (18.8%, n = 384). Yet at least one of the three seeds was compromised in 25.0% of episodes (96 of 384).

## RQ3: change-control gates

Source: `table3_gates.csv`, `mcnemar.csv`, `gates_by_style.csv` and `false_block_causes.csv`. ASR means the attacker's exact write was executed.

| Model | Gate | ASR | Task success (attack) | Task success (control) | False block (control) | Denials per episode |
|---|---|---|---|---|---|---|
| Qwen | none | 13.7% (211/1536) | 53.2% | 56.2% | 0% | 0 |
| Qwen | scope_check | 1.4% (22/1536) | 53.4% | 56.2% | 0% | 0.15 |
| Qwen | ticket_bound | **0%** | 53.1% | 56.2% | 0% | 0.17 |
| Llama | none | 13.5% (26/192) | 47.9% | 16.7% | 0% | 0 |
| Llama | scope_check | 0.5% (1/192) | 12.0% | 8.3% | 16.7% (2/12) | 0.80 |
| Llama | ticket_bound | **0%** | 13.0% | 0% | 16.7% (2/12) | 0.75 |
| Mistral | none | 0.5% (1/191) | 6.3% | 8.3% | 0% | 0 |
| Mistral | scope_check | 0.5% (1/191) | 2.6% | 8.3% | 8.3% (1/12) | 0.15 |
| Mistral | ticket_bound | 0% | 3.1% | 8.3% | 8.3% (1/12) | 0.13 |

**Paired McNemar tests:**
- No gate vs either gate: p < 1e-7 for both Qwen and Llama.
- `ticket_bound` vs `scope_check`, Qwen: 22 vs 0 discordant pairs, p = 5e-7.
- Mistral: no test is meaningful, with 1 event.

**Main findings:**
- **Both gates cut executed attacks by about 10× or more, and `ticket_bound` stopped every one.**
- **`scope_check` lets ticket-confusion attacks through.**
  - All 22 attacks it let through for Qwen are ticket-confusion attacks.
  - Qwen's ticket-confusion ASR is 5.7% under `scope_check`, versus 6.0% with no gate.
  - The attacker's write cites a real, approved ticket for the right device and action, just not the one the operator asked about. This is the case DESIGN D3a predicts.

**Cost depends on the model:**
- **Qwen:** no cost. Task success is unchanged, and there are no false blocks.
- **Llama:** a heavy cost. Task success under attack drops from 48% to 12–13%, and 38.5% of attack episodes contain a false block.
  - In all 152 falsely blocked Llama branches (76 per gate), the denied legitimate write had no `ticket_id`.
  - Only 18 of those 152 later re-issued the write in an allowed form.

**Baseline:** Qwen made an out-of-scope high-impact write in 2 of 96 control runs with no attack (2.1%). Both gates blocked these.

## RQ4: attack style × artifact

Source: `style_carrier.csv`, `logit_delay.csv` and Fig. 4. Rates are attempts with no gate.

| Style | Qwen | Llama | Mistral |
|---|---|---|---|
| direct | 36.5% | 45.8% | 2.1% |
| authority | 8.1% | 4.2% | 0% |
| ticket_confusion | 6.0% | 2.1% | 0% |
| split | 4.4% | 2.1% | 0% |

**Style:** the direct instruction is by far the most effective, at **OR 8.1 versus authority (4.4–14.7)**. Fake authority, ticket confusion and split payloads are weak on their own.

**Artifact:**
- Payloads in **device logs are the least effective (OR 0.45 vs KB articles, p = 0.01)**.
- KB articles, runbooks and tickets are similar.
- Llama is very artifact-sensitive with direct payloads: 75% in KB articles, 67% in runbooks, 33% in tickets and 8% in logs (n = 12 per cell).

## Tool-call format

Source: `format_quality.csv`.

- **Calls written as text** (recovered by the text parser): Qwen 0.5% (50/10,973 LLM calls), Llama 16% (221/1,350), Mistral 81% (872/1,075).
- **Runs with any tool error:** at most 2.5% for every model.
- **Runs that hit the step limit:** 2 of Qwen's 1,632.

## Interpretation notes

1. **Mistral's low attack rate is not robustness.** Mistral completes only 6–8% of tasks and mostly writes its tool calls as text. Its numbers are reported, but they reflect low agent capability and are not used as evidence of robustness.
2. **Gate cost is partly a model property.** Llama's false blocks come from its missing `ticket_id` arguments, not from the gate rule itself. A denial message that tells the agent how to fix a legitimate call might lower this cost; that was not tested.
3. **Direction of the delay effect.** Delayed poisoning is *less* effective than immediate poisoning, but it is still clearly non-zero at d = 3.
