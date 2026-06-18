# Compass Eval Report

Run:

```bash
python -m eval.run_eval --golden-set eval/golden_set/sample_opportunities.json
```

Persist aggregate metrics:

```bash
python -m eval.run_eval --golden-set eval/golden_set/sample_opportunities.json --save
```

Metrics:

- `extraction_accuracy`: average expected-field match across labeled cases.
- `hallucination_rate`: share of cases where extracted optional fields were not grounded in source text.
