# Scripts

How to test the promoter with fake transcripts. Two options: local (all 5 scenarios) or Colab (one scenario, small model).

---

## 1. test_promoter_scenarios.py

Runs all 5 scenarios locally. Uses the promoter from `services/summarizer/llama.py` (real LLM or mock).

### Run from repo root

```bash
cd /Users/zhusiyi/TD1-Capstone
```

**Mock (no model, fast):** promoter always returns 0 recommendations.

```bash
USE_MOCK_LLM=true .venv/bin/python scripts/test_promoter_scenarios.py
```

**Real LLM:** loads LLaMA and runs promoter for each scenario. Needs enough RAM/VRAM and, for gated models, `HF_TOKEN`.

```bash
USE_MOCK_LLM=false .venv/bin/python scripts/test_promoter_scenarios.py
```

### Scenarios

| # | Label | Expectation |
|---|--------|-------------|
| 1 | Random Call (Wrong Number) | 0 recommendations |
| 2 | Lost Debit Card (Upset Client) | 0 or few |
| 3 | University Student Opening Savings | 1–2 (student savings) |
| 4 | Investment Client | 1–2 (investment promos) |
| 5 | Mortgage Renewal | 1–2 (mortgage/cashback) |

### Data

- Fake transcripts and client profiles are defined in the script (aligned with MOCK CLIENT DATA).
- Fake promotion catalog: student savings, credit card discount, investment waiver, mortgage cash back, new savings bonus (promo_id 1–5).

---

## 2. colab_one_scenario_small_model.py

Runs **only Scenario 3** (University student opening savings) in Google Colab with a small model (TinyLlama 1.1B). No HF token; fits free Colab GPU.

### How to run

1. Open Google Colab, create a new notebook.
2. **Runtime → Change runtime type → GPU** (e.g. T4).
3. Create one code cell, paste the **entire** contents of `scripts/colab_one_scenario_small_model.py`.
4. Run the cell.

### What it does

- Loads `TinyLlama/TinyLlama-1.1B-Chat-v1.0` from HuggingFace (public, no login).
- Runs the promoter once on Scenario 3 transcript + client profile + catalog.
- Prints: `[debug] model raw output`, then `Result: no_relevant_flag`, `recommendations` count, and each recommendation (promo_id, name, reason).
- If the model returns 0 recommendations but the transcript clearly matches "student" + "savings" and the catalog has the student promo (promo_id 1), a rule-based fallback adds one recommendation so you can see `recommendations: 1`.

### When to use

- Use **test_promoter_scenarios.py** for full local testing (all 5 scenarios, real or mock).
- Use **colab_one_scenario_small_model.py** when you want a single-scenario test on Colab without a large model or HF token.
