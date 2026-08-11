"""Precompute frozen ESM sequence embeddings for the ranking dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from .train import load_rows


def residue_mean_pool(
    hidden: torch.Tensor,
    batch: dict[str, torch.Tensor],
    special_token_ids: tuple[int | None, ...],
) -> torch.Tensor:
    """Mean-pool biological residues, excluding padding and boundary tokens."""
    mask = batch["attention_mask"].bool()
    for token_id in special_token_ids:
        if token_id is not None:
            mask &= batch["input_ids"].ne(token_id)
    mask = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)


@torch.no_grad()
def embed_sequences(
    sequences: list[str], model_path: Path, output: Path, *, batch_size: int = 64,
    pooling: str = "attention_mean",
) -> dict[str, object]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for ESM embedding extraction")
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModel.from_pretrained(
        model_path, local_files_only=True, use_safetensors=True,
    ).cuda().eval()
    chunks=[]
    for start in range(0, len(sequences), batch_size):
        batch=tokenizer(
            sequences[start:start+batch_size], return_tensors="pt", padding=True,
            truncation=True, max_length=1024,
        )
        batch={key:value.cuda(non_blocking=True) for key,value in batch.items()}
        hidden=model(**batch).last_hidden_state
        if pooling == "residue_mean":
            excluded=(tokenizer.cls_token_id,tokenizer.eos_token_id,tokenizer.pad_token_id)
        elif pooling == "attention_mean":
            excluded=()
        else:
            raise ValueError(f"unknown pooling mode: {pooling}")
        pooled=residue_mean_pool(hidden,batch,excluded)
        chunks.append(pooled.cpu().to(torch.float16))
        if start % (batch_size*50)==0:
            print(json.dumps({"embedded":min(start+batch_size,len(sequences)),"total":len(sequences)}),flush=True)
    embeddings=torch.cat(chunks) if chunks else torch.empty((0,model.config.hidden_size),dtype=torch.float16)
    output.parent.mkdir(parents=True,exist_ok=True)
    torch.save({"sequences":sequences,"embeddings":embeddings},output)
    report={"output":str(output),"sequences":len(sequences),"hidden_size":int(embeddings.shape[1]),"dtype":"float16","model_path":str(model_path),"device":torch.cuda.get_device_name(0),"pooling":pooling}
    output.with_suffix(".json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--model",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=20260803);parser.add_argument("--max-rows-per-source",type=int,default=50_000)
    parser.add_argument("--batch-size",type=int,default=64)
    parser.add_argument("--pooling",choices=("attention_mean","residue_mean"),default="attention_mean")
    parser.add_argument("--split-column")
    parser.add_argument("--include-splits",nargs="+")
    parser.add_argument("--include-task-routes",nargs="+")
    args=parser.parse_args()
    tier_filter = None if args.include_task_routes else {"Gold", "Silver"}
    rows=load_rows(args.input,args.max_rows_per_source,args.seed,tier_filter)
    if args.include_task_routes:
        allowed_routes=set(args.include_task_routes)
        rows=[row for row in rows if row.get("task_route") in allowed_routes]
    if args.split_column and args.include_splits:
        allowed=set(args.include_splits)
        rows=[row for row in rows if row.get(args.split_column) in allowed]
    sequences=sorted({row.get(key,"") for row in rows for key in ("heavy","light","antigen_seq") if row.get(key,"")})
    print(json.dumps(embed_sequences(sequences,args.model,args.output,batch_size=args.batch_size,pooling=args.pooling),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
