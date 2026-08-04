# Stage 4: strict-family mathematical model upgrade

Date: 2026-08-03

## Scope

This stage is restricted to mathematical validation and ranking models. Candidate generation and structure work are outside scope. The objective is to estimate preliminary-round risk under antibody-family shift and select a defensible fallback ensemble.

## Competition check

The official page currently lists the preliminary stage as 2026-03-31 through 2026-08-06, uses Spearman correlation between predicted and measured affinity ranks, and advances 20 teams. The local competition configuration was corrected from 2026-08-07 to 2026-08-06.

## Strict framework-family split

Exact-identity isolation is not enough to measure interpolation across related antibodies. A deterministic record-level stress split was added using a coarse family bucket composed of:

- heavy and light N-terminal framework anchors;
- heavy and light length buckets;
- CDR-H3 length when available;
- sparse heavy and light C-terminal sketches.

Whole buckets are assigned together. The largest family is forced into train, then remaining families are greedily assigned by record load. The resulting frozen split is:

| Fold | Records | Families |
| --- | ---: | ---: |
| Train | 946,480 | 3,648 |
| Validation | 202,817 | 728 |
| Test | 202,817 | 774 |

This is a fast deterministic stress test, not a claim of MMseqs2/CD-HIT identity clustering.

## Pointwise source balancing

For source `s` containing `n_s` sampled training records, each record receives weight

`w_i proportional to n_s^(-p)`

and all weights are normalized to mean one. Three operating points were tested on the same strict-family validation split:

| Source power `p` | Overall Spearman | Pearson | Top-10 enrichment | Stable-source macro | All-source macro |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | **0.1313** | **0.3444** | **1.4994** | 0.1446 | 0.0179 |
| 0.5 | 0.1254 | 0.2818 | 1.4556 | **0.1721** | 0.2252 |
| 1.0 | 0.0956 | 0.1742 | 1.3571 | 0.1480 | **0.2434** |

Full inverse-frequency balancing over-corrects and is rejected. Square-root balancing is retained as a robustness channel.

## Dual-pointwise ensemble

Raw predictions from `p=0` and `p=0.5` were aligned by record ID and linearly blended.

| Weight on `p=0.5` | Overall Spearman | Stable-source macro | All-source macro |
| ---: | ---: | ---: | ---: |
| 0.0 | 0.1313 | 0.1446 | 0.0179 |
| 0.1 | 0.1301 | 0.1548 | 0.0723 |
| 0.2 | 0.1292 | 0.1560 | 0.0787 |
| 0.5 | **0.1298** | **0.1603** | **0.1966** |
| 0.75 | 0.1280 | 0.1678 | 0.2081 |
| 1.0 | 0.1254 | 0.1721 | 0.2252 |

The 50/50 blend is selected as the robust submission setting. The unweighted model remains the maximum-pooled-Spearman setting. The ensemble sacrifices only 0.0015 pooled Spearman while materially improving source balance.

## Strict-family pairwise result

The pair builder and ranker now accept an explicit split column, enabling mathematically valid pair construction under any frozen split. On strict-family train:

- 68,409 preference pairs;
- 71 comparison groups;
- training pair accuracy 0.7904;
- validation records 28,984;
- validation Spearman -0.2146;
- validation top-10 enrichment 0.7794.

This is a clear negative result. The pairwise ranker learns within-family order but reverses under family shift. It must not be included in the robust preliminary submission. The earlier 50/50 pointwise-pairwise ensemble remains descriptive for exact-identity validation only.

## Submission decision

The repository can produce a technically valid fallback ranking submission. The recommended model configuration is now:

1. Gold+Silver supervision only.
2. Two Huber/elastic-net pointwise models using source powers 0 and 0.5.
3. Mean of their predictions, followed by deterministic ranking within the supplied candidate set.
4. Pairwise score excluded from the robust submission unless official validation feedback demonstrates in-distribution behavior.

This model is submission-capable but is not a confident top-20 model. The strict-family Spearman near 0.13 shows that a pretrained representation or stronger antigen-conditioned interaction model is still required for convincing family-shift generalization.
