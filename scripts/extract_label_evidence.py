"""Extract reproducible label-related evidence snippets from the 21 supplied papers.

This is a review aid, not an automatic scientific decision maker.  The generated
JSON keeps page numbers and nearby text so a human can verify the label registry.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader


TERMS = re.compile(
    r"(?i)(dissociation constant|binding affinity|\bK[Dd]\b|IC50|EC50|"
    r"binder|non[- ]binder|fitness|enrichment|neutralization|label(?:ing)?|"
    r"predicted affinity)"
)


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract(pdf: Path, limit: int = 24) -> dict[str, object]:
    reader = PdfReader(pdf)
    snippets: list[dict[str, object]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = compact(page.extract_text() or "")
        for match in TERMS.finditer(text):
            start = max(0, match.start() - 220)
            end = min(len(text), match.end() + 420)
            snippet = text[start:end]
            if snippet and all(item["text"] != snippet for item in snippets):
                snippets.append({"page": page_number, "term": match.group(0), "text": snippet})
            if len(snippets) >= limit:
                break
        if len(snippets) >= limit:
            break
    return {
        "file": str(pdf),
        "pages": len(reader.pages),
        "snippets": snippets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    papers = sorted(args.data_root.rglob("*.pdf"), key=lambda p: str(p))
    result = {"paper_count": len(papers), "papers": [extract(path) for path in papers]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"paper_count": len(papers), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
