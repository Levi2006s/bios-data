from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.neural_ensemble import ensemble_predictions


def test_neural_ensemble_improves_complementary_order(tmp_path: Path) -> None:
    paths=[]
    truth=[0.0,.25,.5,.75,1.0]
    predictions=[[0,.1,.4,1,.8],[.1,0,.6,.7,1]]
    for number,scores in enumerate(predictions):
        path=tmp_path/f"p{number}.csv";paths.append(path)
        with path.open("w",encoding="utf-8",newline="") as handle:
            writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
            for index,(y,score) in enumerate(zip(truth,scores)):writer.writerow([str(index),"s",y,score])
    report=ensemble_predictions(paths,tmp_path/"ensemble.csv")
    assert report["records"]==5
    assert report["overall"]["spearman"]>0.9
