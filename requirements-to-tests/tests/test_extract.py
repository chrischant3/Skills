"""Behaviour tests for scripts/extract.py.

Fixtures are generated on the fly (hand-built .docx XML and PDF bytes, openpyxl for
xlsx), so no binary fixtures live in the repo. Tests that need a missing tool
are skipped rather than failed.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extract  # noqa: E402


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _para(text: str, style: str | None = None, bold: bool = False) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _table(rows: list[list[str]]) -> str:
    cells = lambda r: "".join(f"<w:tc>{_para(c)}</w:tc>" for c in r)  # noqa: E731
    return "<w:tbl>" + "".join(f"<w:tr>{cells(r)}</w:tr>" for r in rows) + "</w:tbl>"


def _docx(body: str, tmp_path: Path) -> Path:
    """Write a minimal Word-style .docx (styled headings, real tables)."""
    import zipfile

    out = tmp_path / "doc.docx"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>',
        )
    return out


def _pdf(pages: list[str], tmp_path: Path) -> Path:
    """Write a minimal text PDF; each page string may hold several lines (no external tools)."""
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not available")
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        None,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for text in pages:
        shown = " T* ".join(f"({line}) Tj" for line in text.split("\n"))
        stream = f"BT /F1 11 Tf 14 TL 72 720 Td {shown} ET".encode()
        objs.append(
            f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream"
        )
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objs)} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path = tmp_path / "doc.pdf"
    path.write_bytes(out)
    return path


def test_docx_blocks_carry_section_and_paragraph_locators(tmp_path):
    doc = _docx(
        _para("3 Security", "Heading1")
        + _para("The system shall lock an account after five failed logins.")
        + _para("3.1 Audit", "Heading2")
        + _para("All admin actions must be logged."),
        tmp_path,
    )
    blocks = extract.extract(doc)
    lockout = next(b for b in blocks if "five failed logins" in b["text"])
    audit = next(b for b in blocks if "admin actions" in b["text"])
    assert "Security" in lockout["loc"]
    assert "Audit" in audit["loc"]
    assert lockout["loc"] != audit["loc"]


def test_docx_tables_are_kept_as_rows(tmp_path):
    doc = _docx(
        _table(
            [["ID", "Requirement"], ["NFR-1", "Search responds in under 2 seconds"]]
        ),
        tmp_path,
    )
    text = "\n".join(b["text"] for b in extract.extract(doc))
    assert "NFR-1" in text and "under 2 seconds" in text
    row = next(b for b in extract.extract(doc) if "NFR-1" in b["text"])
    assert "under 2 seconds" in row["text"], "cells of one row should stay together"


def test_pdf_blocks_are_located_by_page(tmp_path):
    doc = _pdf(
        ["Records are retained for seven years.", "Data is encrypted at rest."],
        tmp_path,
    )
    blocks = extract.extract(doc)
    assert next(b for b in blocks if "seven years" in b["text"])["loc"] == "p1"
    assert next(b for b in blocks if "encrypted" in b["text"])["loc"] == "p2"


def test_docx_bold_short_paragraph_is_treated_as_heading_when_unstyled(tmp_path):
    doc = _docx(
        _para("Data retention", bold=True) + _para("Records are kept for seven years."),
        tmp_path,
    )
    block = next(b for b in extract.extract(doc) if "seven years" in b["text"])
    assert "Data retention" in block["loc"]


def test_pdf_lines_starting_with_requirement_ids_become_separate_blocks(tmp_path):
    doc = _pdf(
        [
            "2. Performance\nNFR-P1 Respond in under 300 ms.\nNFR-P2 Batch completes before 06:00.\n"
            "and funds arrive the same day."
        ],
        tmp_path,
    )
    texts = [b["text"] for b in extract.extract(doc)]
    assert "NFR-P1 Respond in under 300 ms." in texts
    assert (
        "NFR-P2 Batch completes before 06:00. and funds arrive the same day." in texts
    )


def test_pdf_wrapped_line_starting_with_a_number_stays_in_its_paragraph(tmp_path):
    doc = _pdf(
        ["NFR-A2 Restore within 1 hour with no more than\n15 minutes of data loss."],
        tmp_path,
    )
    texts = [b["text"] for b in extract.extract(doc)]
    assert texts == [
        "NFR-A2 Restore within 1 hour with no more than 15 minutes of data loss."
    ]


def test_xlsx_rows_are_labelled_with_headers_and_sheet_row(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NFRs"
    ws.append(["Ref", "Requirement", "Priority"])
    ws.append(["N-7", "Personal data is deleted 30 days after account closure", "Must"])
    path = tmp_path / "reqs.xlsx"
    wb.save(path)

    blocks = extract.extract(path)
    row = next(b for b in blocks if "N-7" in b["text"])
    assert row["loc"] == "NFRs!R2"
    assert "Requirement: Personal data is deleted" in row["text"]
    assert "Priority: Must" in row["text"]


def test_plain_text_and_markdown_are_located_by_line(tmp_path):
    path = tmp_path / "reqs.md"
    path.write_text(
        "# Scope\n\nUsers must be able to export their data.\n", encoding="utf-8"
    )
    blocks = extract.extract(path)
    export = next(b for b in blocks if "export" in b["text"])
    assert export["loc"].startswith("L")


def test_unsupported_extension_raises_clear_error(tmp_path):
    path = tmp_path / "reqs.pages"
    path.write_text("x")
    with pytest.raises(extract.UnsupportedFormat):
        extract.extract(path)


def test_cli_writes_source_md_and_manifest_with_scanned_page_warning(
    tmp_path, monkeypatch
):
    blocks = [
        {"loc": "p1", "text": "Real text on page one."},
        {"loc": "p2", "text": ""},
    ]
    monkeypatch.setattr(extract, "extract", lambda p: blocks)
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF")
    out = tmp_path / "out"
    extract.main([str(src), "--out-dir", str(out)])

    source_md = (out / "source.md").read_text(encoding="utf-8")
    assert "[p1] Real text on page one." in source_md
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["blocks"] == 2
    assert any("p2" in w for w in manifest["warnings"]), (
        "empty PDF page should be flagged as possibly scanned"
    )
