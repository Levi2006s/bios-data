# Stage 2: experiment-aware and ranking-ensemble results

Date: 2026-08-03

## Outcome

Stage 2 establishes a stronger validation-time ranking recipe without changing the leakage-safe identity split from Stage 1. The recommended primary ranking model is now a 50/50 percentile-rank ensemble of the Gold+Silver pointwise regressor and the Gold+Silver pairwise ranker. An assay-aware expert score is retained as a secondary diagnostic output, not as a replacement for the global score.

This is still a sequence-only retrospective benchmark. It is not evidence that the system can predict absolute affinity, neutralization, developability, or wet-lab success for a novel antibody.

## Fixed evaluation protocol

- Canonical records: `data/processed/benchmark_identity_canonical.csv`
- Split column: `split`
- Training tiers: Gold and Silver
- Exact identity: SHA-256 of normalized heavy and light sequences
- Identity assignment: train/validation/test = 70/15/15 by deterministic hash bucket
- Pointwise sampling cap: 50,000 records per source file
- Validation sizes vary slightly by seed because source-level subsampling is seeded
- Stable macro metric: unweighted mean source Spearman for sources with at least 20 validation records

The identity split prevents an exact heavy+light sequence from appearing in multiple folds. It does not yet prevent close sequence homologs, shared lineages, or related antigens from crossing folds.

## Experiment-aware model

The new model has two layers:

1. A global Huber/elastic-net SGD regressor trained on antibody k-mer and physicochemical features.
2. Metric-specific experts for metric groups with at least 200 training records.

Training weights are read from `label_quality` and clipped to `[0.05, 1.0]`. Six experts were trainable in the current Gold+Silver data: EC50, IC50, KD, binding signal, log10 KD-or-IC50, and negative-log10 KD. Missing or undersized metric groups fall back to the global prediction.

### Blend scan, seed 20260803

| Expert weight | Overall Spearman | Top-10 enrichment | Stable-source macro Spearman |
| ---: | ---: | ---: | ---: |
| 0.00 | 0.4072 | 2.4080 | 0.2739 |
| 0.10 | 0.4041 | 2.3551 | 0.2881 |
| 0.20 | 0.4001 | 2.3455 | 0.3038 |
| 0.30 | 0.3943 | 2.3407 | 0.3168 |
| 0.50 | 0.3758 | 2.2590 | 0.3388 |
| 0.75 | 0.3684 | 2.0715 | 0.3677 |
| 1.00 | 0.3646 | 1.8168 | 0.3788 |

There is a real Pareto trade-off. Increasing the expert weight improves source balance but degrades pooled ranking and top-tail recovery. The selected secondary operating point is 20% expert weight. The primary output remains the global score.

### Three-seed stability

| Seed | Global Spearman | 20% expert Spearman | 20% expert stable macro |
| ---: | ---: | ---: | ---: |
| 20260803 | 0.4072 | 0.4001 | 0.3038 |
| 20260804 | 0.3988 | 0.3926 | 0.3043 |
| 20260805 | 0.3955 | 0.3888 | 0.3029 |
| Mean ± sample SD | 0.4005 ± 0.0061 | 0.3938 ± 0.0057 | 0.3036 ± 0.0007 |

The direction and size of the trade-off are stable. The remarkably small macro variation supports keeping the expert channel for robustness analysis, but the pooled Spearman loss prevents making it the default ranking score.

## Pointwise–pairwise validation ensemble

The pointwise and pairwise validation predictions share all 20,794 records in the pointwise validation subset. Scores were converted to tie-aware percentile ranks within `target_id`, then blended. This within-target transformation matches the intended use: ranking antibodies competing under the same experimental target, rather than comparing raw scores across incompatible assays.

| Pairwise weight | Overall Spearman | Top-10 enrichment | Stable-source macro Spearman |
| ---: | ---: | ---: | ---: |
| 0.00 | 0.3468 | 3.1289 | 0.2153 |
| 0.20 | 0.3781 | 4.2728 | 0.2807 |
| 0.40 | 0.3975 | 4.3930 | 0.3673 |
| **0.50** | **0.4034** | **4.4170** | **0.4120** |
| 0.75 | 0.3969 | 4.3641 | 0.4645 |
| 1.00 | 0.3701 | 3.7201 | 0.4781 |

The 50/50 ensemble is the recommended default because it gives the best pooled Spearman and top-10 enrichment while nearly doubling stable-source macro Spearman relative to normalized pointwise alone. A pairwise weight of 0.75 remains a defensible robustness setting when equal source performance matters more than pooled performance.

Raw pointwise Spearman from Stage 1 (about 0.409 for seed 20260803) is not directly comparable to the 0.3468 normalized pointwise endpoint above: the ensemble evaluation deliberately converts every model to within-target percentile ranks before mixing them.

## Reproduction

```bash
PYTHONPATH=src python -m bioos_benchmark.experiment_train \
  --input data/processed/benchmark_identity_canonical.csv \
  --artifact-dir artifacts/experiment_aware_seed_20260804 \
  --seed 20260804 --include-tiers Gold Silver --expert-blend 0.2

PYTHONPATH=src python -m bioos_benchmark.blend_sweep \
  --predictions artifacts/experiment_aware_seed_20260803/predictions.csv \
  --original-blend 0.5 --blends 0 0.1 0.2 0.3 0.5 0.75 1

PYTHONPATH=src python -m bioos_benchmark.ranking.validation_ensemble \
  --pointwise artifacts/baseline_gold_silver_validation/predictions.csv \
  --pairwise artifacts/pairwise_gold_silver_validation/predictions_validation.csv \
  --pairwise-weights 0 0.2 0.4 0.5 0.75 1
```

## What the AI system can do now

The implemented system can:

- audit heterogeneous antibody datasets and recover their usable schema;
- distinguish continuous, binary, weak, and unlabeled supervision;
- normalize incompatible assay labels into source-local ranking targets;
- attach provenance, metric direction, quality tier, and label-quality metadata;
- detect exact duplicate components and quantify cross-study leakage;
- build exact-identity-safe train, validation, and test folds;
- train quality-weighted pointwise models and within-assay pairwise rankers;
- train metric-specific experts with deterministic global fallback;
- evaluate pooled correlation, per-source correlation, and top-tail enrichment;
- blend heterogeneous rankers after target-local percentile calibration;
- score and rank a supplied candidate set and export deterministic ranking files;
- reproduce all decisions through command-line tools, tests, reports, and versioned code.

It cannot yet:

- generate new antibody sequences under biological constraints;
- condition reliably on a novel antigen or epitope;
- model antibody–antigen structure or docking geometry;
- estimate calibrated absolute KD/IC50 across assay types;
- guarantee expression, stability, specificity, immunogenicity, or neutralization;
- claim generalization to close-homology or lineage-held-out antibodies;
- replace wet-lab screening or prospective validation.

## Next engineering stage

The next useful stage is candidate proposal with hard safety rails, not another minor linear-model variant:

1. Add homology-cluster and antigen-held-out evaluations to measure genuine generalization.
2. Add antigen-aware representations only for records with valid antigen sequences.
3. Build a conservative mutation proposal engine around known binders, restricted to configurable CDR positions and mutation budgets.
4. Rank proposals with the 50/50 ensemble while applying sequence-validity, liability, novelty, and uncertainty filters.
5. Export an auditable shortlist with parent sequence, mutations, score components, nearest training neighbor, and out-of-distribution warnings.
6. Treat prospective wet-lab measurements as the only evidence for real affinity improvement.
