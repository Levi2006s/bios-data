"""Extract WordprocessingML tables without requiring python-docx."""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_tables(path:Path)->list[list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        root=ET.fromstring(archive.read("word/document.xml"))
    result=[]
    for table in root.iter(W+"tbl"):
        rows=[];vertical={}
        for tr in table.findall(W+"tr"):
            row=[];column=0
            for tc in tr.findall(W+"tc"):
                props=tc.find(W+"tcPr");span=1;merge=None
                if props is not None:
                    grid=props.find(W+"gridSpan")
                    if grid is not None:span=int(grid.get(W+"val","1"))
                    node=props.find(W+"vMerge")
                    if node is not None:merge=node.get(W+"val","continue")
                paragraphs=[]
                for paragraph in tc.findall(".//"+W+"p"):
                    value="".join(node.text or "" for node in paragraph.iter(W+"t")).strip()
                    if value:paragraphs.append(value)
                value="\n".join(paragraphs)
                if merge=="continue":value=vertical.get(column,value)
                elif merge=="restart":vertical[column]=value
                elif value:vertical.pop(column,None)
                row.extend([value]+[""]*(span-1));column+=span
            rows.append(row)
        width=max((len(row) for row in rows),default=0)
        result.append([row+[""]*(width-len(row)) for row in rows])
    return result


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("input",type=Path);parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    tables=extract_tables(args.input);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle,delimiter="\t")
        for index,table in enumerate(tables):
            if index:writer.writerow([])
            writer.writerow([f"TABLE {index+1}"]);writer.writerows(table)
    summary={"input":str(args.input),"tables":len(tables),"rows":[len(x) for x in tables],"columns":[max(map(len,x),default=0) for x in tables],"output":str(args.output)}
    args.output.with_suffix(".json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
