# Stage 3: conservative candidate proposal

Date: 2026-08-03

## Status

The repository now has a constrained local proposal path around a supplied parent antibody. This is an auditable experiment-prioritization tool, not a de novo antibody generator and not a wet-lab affinity claim.

## Implemented safeguards

- Mutations are limited to the exact CDR-H3 substring supplied by the user.
- The mutation budget is explicit and defaults to at most three substitutions.
- CDR-H3 cysteines are protected by default.
- The user may provide zero-based `mutable_positions`; out-of-range positions fail loudly.
- Every candidate records one-based mutation notation and mutation count.
- The output includes parent score, candidate score, predicted delta, liability delta, and a mutation-count penalty.
- Liability annotations cover N-linked glycosylation motifs, hydrophobic fraction, charge density, cysteine count, deamidation motifs, isomerization motifs, and oxidation-prone methionine/tryptophan counts.
- Every row is labeled `in_silico_unvalidated`.
- A sidecar summary repeats that predictions are retrospective scores, not experimental affinity evidence.

## Smoke test

The command below generated and ranked 20 candidates successfully with the Stage 1 Gold+Silver pointwise model:

```bash
PYTHONPATH=src python -m bioos_benchmark.design \
  --model artifacts/baseline_gold_silver_validation/model.joblib \
  --target examples/target.json \
  --output artifacts/stage3_candidates_smoke.csv \
  --count 20 --max-mutations 2 --seed 20260803
```

The parent retrospective score was 0.48337. Candidate output is intentionally kept under the ignored `artifacts/` directory because these are model-generated research suggestions, not curated source data.

## Remaining gap before prospective use

This first version uses the pointwise model only. Before proposing a costly wet-lab plate, the next implementation should add:

1. Pairwise rescoring against the parent and local candidate pool.
2. Nearest-training-sequence similarity and explicit out-of-distribution warnings.
3. Diversity selection so the shortlist does not consist of near-identical variants.
4. ANARCI/IMGT numbering so mutation constraints can be specified in biological numbering rather than substring offsets.
5. Antigen-aware scoring and structure-based rejection when trustworthy antigen/epitope context is available.
6. A final human review gate for developability, manufacturability, biological plausibility, and experimental design.
