from __future__ import annotations

import torch

from bioos_benchmark.esm_finetune import make_collate, make_grad_scaler


class TinyTokenizer:
    def __call__(self,values,**kwargs):return {"input_ids":torch.ones(len(values),3,dtype=torch.long),"attention_mask":torch.ones(len(values),3,dtype=torch.long)}


def test_finetune_collate_shapes():
    row={"heavy":"AAA","light":"CCC","antigen_seq":"DDD","score":".5"}
    heavy,light,antigen,labels,weights,indices=make_collate(TinyTokenizer())([(row,1.0,7)])
    assert heavy["input_ids"].shape==(1,3)
    assert labels.tolist()==[.5] and indices.tolist()==[7]


def test_grad_scaler_uses_legacy_api_when_modern_api_is_missing(monkeypatch):
    sentinel=object()
    monkeypatch.delattr(torch.amp,"GradScaler",raising=False)
    monkeypatch.setattr(torch.cuda.amp,"GradScaler",lambda:sentinel)
    assert make_grad_scaler() is sentinel
