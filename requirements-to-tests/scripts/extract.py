#!/usr/bin/env python3
"""Turn a requirements document into located text blocks the analysis can cite.

Every block carries a locator so each extracted requirement can point back to where
it came from (Gause & Weinberg: "Every requirement should be traceable to its source"):

    PDF          p<page>                         e.g. p12
    DOCX         <nearest heading> ¶<n>          e.g. 3.1 Audit ¶14
    XLSX / CSV   <sheet>!R<row>                  e.g. NFRs!R7
    TXT / MD     L<line>                         e.g. L42
    DOC/RTF/ODT  converted with macOS textutil, then located by line

Usage:
    extract.py <document> --out-dir <dir>

Writes <dir>/source.md (one "[loc] text" line per block) and <dir>/manifest.json
(counts plus warnings, e.g. PDF pages with no text that probably need OCR).

Dependencies: stdlib, openpyxl (xlsx), poppler's pdftotext (pdf), textutil (doc/rtf/odt).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADING_STYLE = re.compile(r"^(heading\s*\d|title|subtitle)$", re.IGNORECASE)
MIN_PAGE_CHARS = 20
# A line that starts a new item even without a blank line before it: a requirement ID
# ("NFR-P1", "SEC-2", "R12"), a numbered heading/item ("2.", "3.1.4") or a bullet.
ITEM_START = re.compile(r"^\s*(?:[A-Z]{1,6}(?:[-_.]?[A-Z]{1,3})?[-_.]?\d+(?:[.\-]\d+)*\b|\d+(?:\.\d+)*\.\s|\d+(?:\.\d+)+\s|[\u2022\u25aa\-*]\s)")


class UnsupportedFormat(ValueError):
    """Raised when the file extension is not one the extractor understands."""


def extract(path: Path) -> list[dict]:
    """Return the document as a list of {"loc", "text"} blocks in reading order.

    Raises UnsupportedFormat for unknown extensions.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    handlers = {
        ".pdf": _extract_pdf,
        ".docx": _extract_docx,
        ".xlsx": _extract_xlsx,
        ".xlsm": _extract_xlsx,
        ".csv": _extract_csv,
        ".txt": _extract_lines,
        ".md": _extract_lines,
        ".doc": _extract_via_textutil,
        ".rtf": _extract_via_textutil,
        ".odt": _extract_via_textutil,
    }
    if suffix not in handlers:
        raise UnsupportedFormat(f"Cannot extract {suffix or 'extensionless'} files: {path.name}")
    return handlers[suffix](path)


def _extract_pdf(path: Path) -> list[dict]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext (poppler) is required for PDF files: brew install poppler")
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    blocks = []
    for number, page in enumerate(pages, start=1):
        paragraphs = [p for p in _split_items(page) if p]
        if not paragraphs:
            blocks.append({"loc": f"p{number}", "text": ""})
        blocks.extend({"loc": f"p{number}", "text": p} for p in paragraphs)
    return blocks


def _split_items(page: str) -> list[str]:
    """Split page text into paragraphs at blank lines and at lines that start a new item."""
    items: list[list[str]] = [[]]
    for line in page.splitlines():
        if not line.strip() or ITEM_START.match(line):
            items.append([])
        if line.strip():
            items[-1].append(line)
    return [_squash(" ".join(lines)) for lines in items]


def _extract_docx(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{W_NS}body")
    blocks: list[dict] = []
    heading = ""
    count = 0
    for element in list(body) if body is not None else []:
        if element.tag == f"{W_NS}p":
            text = _para_text(element)
            if not text:
                continue
            if _is_heading(element, text):
                heading = text
                continue
            count += 1
            blocks.append({"loc": _docx_loc(heading, count), "text": text})
        elif element.tag == f"{W_NS}tbl":
            for row in element.iter(f"{W_NS}tr"):
                cells = [" ".join(_para_text(p) for p in cell.iter(f"{W_NS}p")).strip() for cell in row.iter(f"{W_NS}tc")]
                if any(cells):
                    count += 1
                    blocks.append({"loc": _docx_loc(heading, count), "text": " | ".join(cells)})
    return blocks


def _docx_loc(heading: str, count: int) -> str:
    return f"{heading[:60]} ¶{count}" if heading else f"¶{count}"


def _para_text(p: ET.Element) -> str:
    return _squash("".join(t.text or "" for t in p.iter(f"{W_NS}t")))


def _is_heading(p: ET.Element, text: str) -> bool:
    """Styled headings win; otherwise a short, wholly bold line with no full stop counts.

    The fallback exists because many real specs are formatted by hand, not with styles.
    """
    style = p.find(f"{W_NS}pPr/{W_NS}pStyle")
    if style is not None and HEADING_STYLE.match(style.get(f"{W_NS}val", "").replace("Heading", "Heading ")):
        return True
    if p.find(f"{W_NS}pPr/{W_NS}outlineLvl") is not None:
        return True
    runs = [r for r in p.iter(f"{W_NS}r") if "".join(t.text or "" for t in r.iter(f"{W_NS}t")).strip()]
    all_bold = bool(runs) and all(r.find(f"{W_NS}rPr/{W_NS}b") is not None for r in runs)
    return all_bold and len(text.split()) <= 12 and not text.endswith((".", ":", ";"))


def _extract_xlsx(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    blocks = []
    for ws in wb.worksheets:
        headers: list[str] | None = None
        for row_number, row in enumerate(ws.iter_rows(values_only=True), start=1):
            values = ["" if v is None else _squash(str(v)) for v in row]
            if not any(values):
                continue
            if headers is None:
                headers = [v or f"Col{i + 1}" for i, v in enumerate(values)]
                continue
            blocks.append({"loc": f"{ws.title}!R{row_number}", "text": _label_row(headers, values)})
    return blocks


def _extract_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    blocks = []
    headers = None
    for row_number, row in enumerate(rows, start=1):
        values = [_squash(v) for v in row]
        if not any(values):
            continue
        if headers is None:
            headers = [v or f"Col{i + 1}" for i, v in enumerate(values)]
            continue
        blocks.append({"loc": f"{path.stem}!R{row_number}", "text": _label_row(headers, values)})
    return blocks


def _label_row(headers: list[str], values: list[str]) -> str:
    pairs = []
    for i, value in enumerate(values):
        if value:
            name = headers[i] if i < len(headers) else f"Col{i + 1}"
            pairs.append(f"{name}: {value}")
    return "; ".join(pairs)


def _extract_lines(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [{"loc": f"L{n}", "text": _squash(line)} for n, line in enumerate(lines, start=1) if line.strip()]


def _extract_via_textutil(path: Path) -> list[dict]:
    if not shutil.which("textutil"):
        raise RuntimeError(f"{path.suffix} needs macOS textutil; save the file as .docx or .pdf instead")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "converted.txt"
        subprocess.run(["textutil", "-convert", "txt", str(path), "-output", str(out)], check=True)
        return _extract_lines(out)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _warnings(blocks: list[dict]) -> list[str]:
    warnings = []
    pages: dict[str, int] = {}
    for block in blocks:
        if re.fullmatch(r"p\d+", block["loc"]):
            pages[block["loc"]] = pages.get(block["loc"], 0) + len(block["text"])
    for loc, chars in pages.items():
        if chars < MIN_PAGE_CHARS:
            warnings.append(f"{loc}: little or no text; probably a scanned image or diagram. Check it by eye or OCR it.")
    if not any(b["text"] for b in blocks):
        warnings.append("No text extracted at all.")
    return warnings


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: extract a document into source.md + manifest.json."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    blocks = extract(args.document)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Source: {args.document.name}", ""]
    lines += [f"[{b['loc']}] {b['text']}" for b in blocks if b["text"]]
    (args.out_dir / "source.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "document": str(args.document),
        "blocks": len(blocks),
        "words": sum(len(b["text"].split()) for b in blocks),
        "warnings": _warnings(blocks),
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
