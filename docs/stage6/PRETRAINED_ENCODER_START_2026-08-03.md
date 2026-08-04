# Stage 6: pretrained protein encoder start

Date: 2026-08-03

## Status

The pretrained-encoder stage has started. Hugging Face tooling and Transformers dependencies are installed, and the first ESM-2 checkpoint has been downloaded into the BioOS-local ignored model cache.

## Frozen model identity

- Repository: `facebook/esm2_t6_8M_UR50D`
- Snapshot revision: `c731040fcd8d73dceaa04b0a8e6329b345b0f5df`
- Cache: `models/huggingface/`
- Cache size after download: approximately 89 MB
- Hidden size: 320
- GPU smoke test: successful on NVIDIA GeForce RTX 4090
- Smoke-test allocated VRAM: approximately 36.9 MiB

The Transformers loader reports newly initialized pooler parameters. The planned pipeline does not use that pooler: it uses attention-mask-aware mean pooling of `last_hidden_state`.

## Planned experiment

1. Freeze ESM-2 and precompute unique heavy, light, and antigen sequence embeddings.
2. Cache embeddings under ignored `artifacts/stage6/` with snapshot revision metadata.
3. Train an interaction head using antibody concatenation, antibody-antigen absolute difference, and elementwise product.
4. Evaluate on the same frozen strict-family validation records used by Stage 5.
5. Compare directly against the current two-seed CNN rank ensemble Spearman of 0.3780.

## Frozen ESM interaction-head result

The controlled comparison is complete for seed 20260803. The ESM backbone remained frozen; only the antibody-antigen interaction head was trained.

| Metric | CNN rank ensemble | Frozen ESM head |
| --- | ---: | ---: |
| Strict-family Spearman | 0.3780 | **0.4456** |
| Pearson | 0.4525 | **0.5268** |
| Top-10 enrichment | 1.7472 | **2.4340** |

The best ESM checkpoint occurred at epoch 39 with 24,559 training records and 8,281 validation records. This model is now the primary valid-antigen ranking candidate. A second fixed-data seed is still required before freezing the final ensemble.

The second fixed-data ESM seed reached 0.4115 and reduced performance at every positive ensemble weight, so it is excluded. The CNN models were complementary: a percentile-rank ensemble of 65% best ESM, 17.5% CNN seed 20260803, and 17.5% CNN seed 20260804 reached strict-family Spearman **0.4571**, Pearson **0.5137**, and top-10 enrichment **2.6750**. It is the current recommended valid-antigen model.
