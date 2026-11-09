#!/usr/bin/env python3
"""Regenerate the eval input documents in evals/files/ (docx, pdf, xlsx).

The documents are fictional and deliberately flawed: vague NFRs, missing tails, hidden
functions, risky assumptions and absent privacy rules. That lets the evals check that the
skill finds them.

Dev-only dependencies: openpyxl (xlsx) and fpdf2 (pdf): `pip install openpyxl fpdf2`. fpdf2 is
used rather than an OS print tool so the PDF builds identically on any machine and records
nothing about the machine that built it.
"""

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "files"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _p(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _tbl(rows):
    return "<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"


def clinic_docx():
    body = "".join([
        _p("MyClinic Patient Portal - Requirements Specification v0.3", "Title"),
        _p("1 Introduction", "Heading1"),
        _p("MyClinic runs 14 GP surgeries. The portal lets registered patients book appointments, see their records and message their clinician. It will be available on the public internet."),
        _p("2 Booking", "Heading1"),
        _p("BK-1 Patients can book an appointment with any available clinician up to 4 weeks ahead."),
        _p("BK-2 Patients can cancel an appointment up to 24 hours before it starts."),
        _p("BK-3 The system will send a reminder by SMS the day before."),
        _p("3 Patient records", "Heading1"),
        _p("REC-1 Patients can view their test results and medication list."),
        _p("REC-2 Patients can download their records."),
        _p("REC-3 Clinicians can view patient records."),
        _p("4 Security", "Heading1"),
        _p("SEC-1 The system shall be secure and follow industry best practice."),
        _p("SEC-2 Accounts are locked after 5 failed login attempts."),
        _p("SEC-3 Passwords must be strong."),
        _p("SEC-4 Administrators can see all data in order to support users."),
        _p("5 Performance and availability", "Heading1"),
        _p("The following table lists the performance requirements."),
        _tbl([["ID", "Requirement", "Priority"],
              ["PERF-1", "The portal must be fast.", "High"],
              ["PERF-2", "The system should support up to 500 users.", "High"],
              ["PERF-3", "Availability of 99.9%.", "Medium"]]),
        _p("6 Data", "Heading1"),
        _p("DATA-1 Patient data will be handled in line with GDPR."),
        _p("DATA-2 Data is deleted when it is no longer needed."),
        _p("DATA-3 Backups are taken nightly."),
        _p("DATA-4 Test results are imported every 15 minutes from the lab system."),
        _p("7 Assumptions", "Heading1"),
        _p("A-1 Only registered patients will use the portal, and clinic staff are trusted, so detailed audit logging is not required."),
    ])
    path = OUT / "myclinic-portal-spec-v0.3.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>')
    return path


# A fixed timestamp keeps the PDF byte-identical across rebuilds, so git only sees real changes.
PDF_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def payouts_pdf(out=OUT):
    """Write the payouts NFR PDF (one section group per page) to `out` and return its path."""
    pages = [
        """Merchant Payouts API - Non-Functional Requirements (Draft 2)

1. Context
The Payouts API lets merchants request payouts of their settled balance to a UK bank
account. It is called by merchant back-office systems and by our own dashboard.
Peak volume is Black Friday, when traffic is roughly five times a normal day.

2. Performance
NFR-P1 The API must respond in under 300 ms for 95% of requests.
NFR-P2 The nightly payout batch must complete before 06:00 so funds arrive the same day.
NFR-P3 The platform must handle 2 million payout requests per day.
NFR-P4 The dashboard should load quickly.
""",
        """3. Availability and recovery
NFR-A1 The API must be available 99.95% of the time per month, excluding planned maintenance.
NFR-A2 In a disaster, the service must be restored within 1 hour with no more than
15 minutes of data loss.
NFR-A3 Webhooks to merchants are retried if delivery fails.

4. Security
NFR-S1 Merchants authenticate with API keys.
NFR-S2 Each merchant is limited to 100 requests per second.
NFR-S3 Full card numbers are never stored; bank account numbers are encrypted.
NFR-S4 The API must comply with PCI DSS.
""",
        """5. Data and audit
NFR-D1 Every payout request and status change is recorded in an audit log kept for 7 years.
NFR-D2 Card and bank details must be masked in application logs.
NFR-D3 Merchants can export their payout history as CSV.
NFR-D4 A payout, once confirmed, is never processed twice.
""",
    ]
    pdf = FPDF(format="A4")
    pdf.set_creation_date(PDF_DATE)
    pdf.set_font("Courier", size=10)
    for page in pages:
        pdf.add_page()
        for line in page.splitlines():
            pdf.multi_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    path = Path(out) / "payouts-api-nfrs-draft2.pdf"
    pdf.output(str(path))
    return path


def crm_xlsx():
    rows = [
        ("MIG-01", "Migration", "All customer records are migrated from the legacy CRM to the new CRM.", "Must", "Data team"),
        ("MIG-02", "Migration", "No data is lost during migration.", "Must", "Data team"),
        ("MIG-03", "Migration", "Duplicate customers are merged.", "Should", "Data team"),
        ("MIG-04", "Migration", "The migration is completed over a single weekend.", "Must", "PMO"),
        ("MIG-05", "Migration", "Legacy CRM remains available read-only for 90 days after go-live.", "Should", "IT Ops"),
        ("DAT-01", "Data protection", "Marketing consent flags are carried across.", "Must", "DPO"),
        ("DAT-02", "Data protection", "Customers inactive for more than 6 years are not migrated.", "Must", "DPO"),
        ("DAT-03", "Data protection", "Sales users only see customers in their own region.", "Must", "Sales Ops"),
        ("DAT-04", "Data protection", "Customer records can be exported on request.", "Could", "DPO"),
        ("REP-01", "Reporting", "Month-end revenue reports match the legacy reports.", "Must", "Finance"),
        ("ACC-01", "Access", "Users sign in with company SSO.", "Must", "IT Ops"),
        ("PER-01", "Performance", "Search response times are the same or better than the legacy CRM.", "Should", "Sales Ops"),
        ("PER-02", "Performance", "The system supports all 350 sales users.", "Must", "Sales Ops"),
        ("INT-01", "Integration", "Orders from the web shop appear in the CRM within 5 minutes.", "Should", "IT Ops"),
    ]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Requirements"
    ws.append(["ID", "Area", "Requirement", "Priority (MoSCoW)", "Owner"])
    for r in rows:
        ws.append(r)
    path = OUT / "crm-migration-requirements-register.xlsx"
    wb.save(path)
    return path


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for make in (clinic_docx, payouts_pdf, crm_xlsx):
        print(make())
