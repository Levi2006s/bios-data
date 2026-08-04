# Stage 5: GPU antibody-antigen dual encoder

Date: 2026-08-03

## Outcome

The strict-family affinity model now uses explicit antibody-antigen interactions. A sparse CPU interaction baseline improved strict-family Spearman from 0.1313 to 0.2102. A GPU CNN dual encoder further improved valid-antigen Spearman to approximately 0.36, and a two-seed percentile-rank ensemble reached 0.3780.

## GPU recovery

The rented RTX 4090 was visible on PCIe and initialized by the NVIDIA 550.78 kernel module, but `/dev/nvidia*` character devices were absent. Running `nvidia-modprobe -u -c=0` created the device nodes. Verification then reported:

- NVIDIA GeForce RTX 4090;
- 24,564 MiB VRAM;
- PyTorch CUDA available with one device;
- successful CUDA tensor execution.

Training used the GPU. Observed initial usage was about 978 MiB VRAM and 5% utilization; CPU tokenization and data loading were the bottleneck rather than GPU compute.

## Sparse interaction baseline

The baseline adds hashed antibody 3-mer by antigen 3-mer cross tokens to the additive k-mer representation.

| Metric | Additive baseline | Interaction baseline |
| --- | ---: | ---: |
| Strict-family overall Spearman | 0.1313 | **0.2102** |
| Pearson | 0.3444 | **0.4142** |
| All-source macro Spearman | 0.0179 | **0.1015** |

On the 8,281 validation records with valid antigen sequence, Spearman was 0.2289. The missing-antigen subset was negative, confirming that antigen-conditioned and fallback paths must remain separate.

## Neural architecture

- independent heavy-chain, light-chain, and antigen CNN encoders;
- learned amino-acid embeddings;
- multi-kernel convolutions and global max pooling;
- concatenated antibody representation;
- projected antigen representation;
- absolute antibody-antigen difference and elementwise product;
- MLP regression head;
- source-square-root weighting and Smooth-L1 loss;
- best checkpoint selected by strict-family validation Spearman.

Training uses only Gold+Silver rows with valid antigen sequence: 24,559 sampled training records and 8,281 validation records for the fixed data seed.

## Results

| Model | Best epoch | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: | ---: |
| Seed 20260803 | 6 | **0.3637** | 0.4985 | **1.4942** |
| Seed 20260804, fixed data | 6 | 0.3512 | 0.4939 | 1.3616 |
| Equal percentile-rank ensemble | — | **0.3780** | — | — |

Extending the first model to 12 epochs showed validation overfitting after epoch 6 even as training loss decreased. Six epochs is therefore the current default early-stopping window.

Adding the sparse linear score to the neural ensemble reduced Spearman at every tested positive weight and is rejected.

## Submission routing

- Valid antigen sequence: two-seed neural percentile-rank ensemble.
- Missing or invalid antigen sequence: sparse interaction/additive fallback, explicitly flagged as lower confidence.
- Pairwise family-shift model: excluded because its strict-family Spearman was negative.

The model is substantially stronger than the previous baseline but is still a compact CNN trained from scratch. A pretrained antibody/protein encoder remains the next model upgrade.
