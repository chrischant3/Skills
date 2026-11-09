---
name: requirements-to-tests
description: >-
  Reads a requirements document (PDF, Word, xlsx/csv register, or text) and produces a traceable
  analysis: requirements extracted and classified, ambiguities exposed, missing requirements raised as
  questions, and test scenarios drafted - with most depth on non-functional requirements: security,
  performance/capacity/availability, and data handling (privacy, retention, integrity, migration,
  backup). Outputs a Markdown report plus an xlsx workbook. Grounded in Gause & Weinberg's Exploring
  Requirements, example mapping/BDD and published testing books, with OWASP ASVS, GDPR-style privacy
  law and ISO 25010 as labelled external checklists. Use whenever the user shares a spec, PRD, SoW,
  tender/RFP, requirements register, story export or NFR list and wants requirements identified,
  reviewed, made testable, or turned into test scenarios, acceptance criteria or a test plan - or asks
  "what's missing from this spec" or "what should we ask the client". Not for unit tests against
  existing code.
---

# Requirements to test scenarios

Turn a requirements document into four things:
- requirements that can be traced back to the document
- ambiguities made visible
- questions worth asking
- draft test scenarios, deepest for **security, performance and data handling**

This follows Gause & Weinberg: "The fundamental problem of requirements definition is ambiguity". The job is to find the ambiguity and put it in front of people, not to paper over it.

This file is enough to complete the task. The files in `references/` add depth: load one only when the table in [When to load a reference](#when-to-load-a-reference) says so, or when the user asks for it.

## Before you start

- `<skill>` below means the folder containing this file. Call scripts by absolute path.
- Needs `python3` (3.10+) and `openpyxl` (`pip install openpyxl`). PDFs need `pdftotext` from poppler (`brew install poppler`, `apt install poppler-utils`). `.doc`, `.rtf` and `.odt` need macOS `textutil`; on other systems, ask the user to save the file as `.docx` or `.pdf`.
- If a dependency is missing, tell the user the install command. Don't fall back to guessing the document's contents.

## Principles (why the workflow looks like this)

- **Trace everything.** Every requirement carries a verbatim quote and a locator from the source. Every scenario traces to requirement IDs. The build script refuses to write outputs when traceability is broken.
- **Don't invent requirements.** If you expected something (e.g. an erasure policy) and didn't find it, that is a *gap* and a *question*, not a requirement. A requirement you derived from a stated one gets `origin: implied`, with the reason given.
- **Don't resolve ambiguity silently.** Where the document is vague, draft the scenario anyway, but mark it `provisional`, state the assumption, and link it to the question that would settle it. Drafts now plus questions are more useful than waiting for answers.
- **Attributes modify functions.** An NFR like "the system shall be secure" is not tested in the abstract. Attach it to the functions it qualifies. A security or data statement that is really a verb ("log failed sign-ins", "delete after 30 days") is a hidden function, and gets tested as one.
- **Measurable or asked.** Every NFR either has a measure (scale, meter, constraint, target) or has a question asking for one.
- **Label sources.** `BOOK:` for published books on requirements and testing, `EXT:` for external standards and regulations. The books supply the method; checklist content for security, performance engineering and privacy law comes from external standards, and the reader should be able to see that.

## Workflow

### 1. Set up and extract
Default output folder: `<input folder>/<input stem>-requirements/`. Use a different folder if the user names one. Requirements documents are often confidential: keep all processing local, and don't upload them or paste large parts into other tools.

```bash
python3 <skill>/scripts/extract.py "<document>" --out-dir "<out>"
```

This writes `source.md` (one `[locator] text` line per paragraph, table row or spreadsheet row) and `manifest.json`. Locators look like `p12` (PDF page), `3.1 Audit ¶14` (Word heading and paragraph), `NFRs!R7` (sheet and row) or `L42` (text line).

Read the manifest warnings. Pages with no text are probably scans or diagrams, and requirements often hide in diagrams and tables. Tell the user which pages were skipped, and offer to read them as images.

Read `source.md` in full. For long documents (more than about 30k words), work through it section by section, keeping a running list. Don't skim.

### 2. Understand the context
Before classifying anything, note:
- what the product is
- who uses it, including who must be kept *out*
- what environment it runs in (public internet? personal data? money?)
- which regimes apply: the privacy law for the product's jurisdiction (e.g. EU GDPR, UK GDPR, CCPA), PCI DSS for card data, sector rules (e.g. HIPAA)

These root answers decide how much security and data depth is warranted. If they're unclear, they become **root** questions. Don't assume a jurisdiction the document doesn't support.

### 3. Functions, then requirements
1. List the **functions** (verbs the product performs). Include hidden ones (users shouldn't notice them, e.g. audit logging) and opaque ones (some groups must not know they exist, e.g. fraud checks), which often only appear in NFR or security sections.
2. Extract **every requirement statement**. Keep the document's own IDs (`NFR-12 (NFRs!R7)`). Classify each one:

   | `kind` | Meaning | Quick test |
   |---|---|---|
   | function | Something the product does | "The product should ⟨it⟩" reads as a sentence |
   | attribute | How well a function is done | An adjective: fast, secure, reliable |
   | constraint | A mandatory, objectively checkable condition on an attribute | Has a yes/no check: "p95 < 2 s at 400 users" |
   | preference | A desirable but optional condition | "as fast as possible", "minimise" |
   | expectation | What users expect beyond what's written | Usually unstated; find it by asking |
   | imposition | Forced by law, standard or authority | Names a regulation, policy or standard |
   | assumption | A decision made by default or bias | "internal network only", "users are trusted" — challenge it |

   - `category`: functional / security / performance / data / reliability / usability / compatibility / maintainability / portability / safety / operability / other
   - `applies_to`: function IDs, or `product-wide` only if it genuinely applies everywhere (cost, safety, product-level regulation)
   - `priority`: must / want / ignore as the document states it; `unconfirmed` if it doesn't. "Shall" alone doesn't prove a constraint.
   - `measurable`, plus `measure` for every NFR (Gilb's fields): **scale** (what is measured, with units), **meter** (how: tool, sample, conditions), **benchmark** (current value), **constraint** (minimum acceptable), **target** (desired). Always ask for a tail or maximum as well as a percentile, and state the conditions (load, data volume, degraded mode). A number with no conditions is not testable.
3. Headings, rationale and examples in the document are not requirements, but they are useful context.

### 4. Ambiguity pass
Apply these to every NFR and every high-risk function:
- **Surface words**: comparatives (fast, secure, robust, appropriate), collective nouns (users, data, records — which ones?), hidden limits (applicable, where possible, standard), optimisation words (minimise, as … as possible), reassurances ("standard security", "no problem").
- **Stress each word**: "*Users* must be able to delete *their* data *immediately*" → which users? data created by them or about them? immediately in the UI, or purged from backups?
- **Persona poll**: for each high-risk requirement, answer a numeric question ("how many concurrent users?", "how long until data is gone?") as a developer, tester, operator, attacker, auditor and end user. A wide spread shows ambiguity.
- **Solutions posing as requirements** ("use Redis"): ask what function or attribute they serve.

Record each real ambiguity with its competing readings. Keep the list to ambiguities that would change a design or a test. Order them by closeness to the root: "public internet or internal?" outranks "which date format?".

### 5. Gap pass for the focus areas
For each focus area that applies to *this* product, go through the matching reference file's gap checklist (see the table below). Record a gap only if it plausibly applies, and say why. A static brochure site does not need a lockout policy. Each gap gets a question.

The core gaps to check even without loading a reference:
- **Security**: authentication and lockout, session timeout, who may see *other people's* records, input handling, encryption in transit and at rest, which security events are logged and who responds.
- **Performance**: response time per key operation (percentile *and* tail), peak load profile, batch windows, availability target, behaviour when a dependency is down, RTO and RPO.
- **Data**: what personal data and why, retention period per record type and what happens at expiry, erasure and other data-subject rights, audit logging, backup and restore tested, migration reconciliation and rollback, no personal data in logs or test environments.

### 6. Questions
Write each question so the answer validates itself: ask what, which or how (not yes/no), and ask for typical *and* untypical examples. Useful prompts: Who must the system be *unfriendly* to? For every "must not", what happens instead (message, audit record, alert)? What must always be true, and what must never happen? Where does that number come from?

Each question gets:
- who to ask
- why it matters
- what it blocks
- a level: `root` (changes everything below it), `branch` or `twig`

Merge duplicates. A short, sharp question list is worth more than a long one.

### 7. Draft scenarios
- Run a **"What if…"** pass for each function across the range of use: `normal`, `abnormal-reasonable` and `abnormal-unreasonable` (misuse, attack, failure). "No sane person would do that" is not a reason to skip a case.
- Turn every threshold into **boundary examples**: "lock after 5 failures" → 4 not locked, 5 locked; "retain 7 years" → day before, day of, day after expiry.
- For each step that can fail, write the **failure** as its own scenario: `Given ⟨state⟩ / When ⟨step fails⟩ / Then ⟨handling⟩`.
- Pick the format per scenario:

  | `format` | Use for | Fields |
  |---|---|---|
  | `gherkin` | A behavioural rule with a trigger (lockout, deny and audit, retention purge) | `given[]`, `when`, `then[]` |
  | `measurement` | A quantitative NFR (latency, throughput, availability, RTO/RPO) | `measurement{metric, load_profile, environment, threshold, warning?, oracle}` |
  | `checklist` | A cross-cutting risk with no single trigger (hardening, log hygiene) | `items[]` |
  | `charter` | Exploration where the oracle is judgement ("Explore ⟨target⟩ with ⟨resources⟩ to discover ⟨information⟩") | `items[]` |

- Gherkin rules: one `When`; no "or" in any step; at most about five steps; business language, no clicks or URLs; one rule per scenario.
- Depth: every non-ignored requirement gets at least one scenario. Security, performance and data requirements get boundary or counter-examples plus at least one abnormal-unreasonable case. For NFRs, consider both a `pre-release` check and a `production` monitor (`layer`).
- Set `risk` (likelihood × consequence) and give every scenario a `basis`.
- Where the document leaves the outcome or threshold open: `status: provisional`, list each assumption in `assumptions[]` linked to its question, and say where the assumed value comes from ("assumed p95 < 2 s, a common web norm; not in the document").

### 8. Build and check
Write `<out>/analysis.json` in this shape (IDs unique across all lists):

```json
{
  "document": {"title": "", "source_file": "", "analysed_on": "YYYY-MM-DD"},
  "functions": [{"id": "F-01", "name": "", "visibility": "evident|hidden|opaque|translucent|frill", "source_ref": ""}],
  "requirements": [{"id": "R-001", "text": "verbatim", "source_ref": "NFR-12 (NFRs!R7)", "kind": "", "category": "",
                    "applies_to": ["F-01"], "priority": "", "origin": "stated|implied", "measurable": false,
                    "measure": {"scale": "", "meter": "", "benchmark": "", "constraint": "", "target": ""},
                    "ambiguities": [{"phrase": "", "readings": [], "heuristic": ""}], "question_ids": ["Q-01"], "basis": []}],
  "questions": [{"id": "Q-01", "question": "", "why": "", "ask": "role", "level": "root|branch|twig", "blocks": ["R-001"]}],
  "scenarios": [{"id": "S-001", "title": "Area - specific behaviour", "req_ids": ["R-001"], "category": "", "format": "gherkin",
                 "range": "normal", "status": "ready|provisional", "layer": "pre-release|pipeline|production",
                 "risk": "high|medium|low", "basis": ["BOOK: FIFTY boundaries"],
                 "assumptions": [{"text": "", "question_id": "Q-01"}], "given": [], "when": "", "then": []}],
  "gaps": [{"category": "", "missing": "", "why_it_matters": "", "basis": [], "question_id": "Q-01"}]
}
```

`basis` entries are `BOOK: <abbrev> <chapter or topic>` or `EXT: <standard> <section or topic>`. The abbreviations used most:

| Abbrev | Book | Abbrev | Book |
|---|---|---|---|
| ER1 / ER2 | Gause & Weinberg, *Exploring Requirements* 1 / 2 | FIFTY | Adzic et al., *Fifty Quick Ideas to Improve Your Tests* |
| LBR | Kelly, *A Little Book about Requirements and User Stories* | DISC / FORM | Nagy & Rose, *Discovery* / *Formulation* (BDD Books) |
| PS | Weinberg, *Perfect Software and Other Illusions about Testing* | MINI / UNIFY | Cockburn, use-case books |
| DOH | Kim et al., *The DevOps Handbook* | Clokie | Clokie, *A Practical Guide to Testing in DevOps* |

Cite OWASP ASVS by chapter *name* ("EXT: OWASP ASVS Authentication"), not number. Then run:

```bash
python3 <skill>/scripts/build_outputs.py "<out>/analysis.json" --out-dir "<out>" --stem "<input stem>"
```

- **Errors** (broken references, bad values): fix them in analysis.json and rerun.
- **Warnings**: fix the ones that are your own slips (a missing basis, "or" in a step, a provisional scenario with no assumption). Leave the ones that are genuine findings about the document (an untestable NFR, an NFR attached to no function). They appear in the report's Validation notes on purpose.

Then self-check before replying:
- Spot-check five requirement quotes against `source.md`.
- Confirm no gap was entered as a stated requirement.
- Confirm every provisional value is visibly marked as an assumption.

### 9. Reply
Keep the chat reply short. Give:
- the two output file paths (report and xlsx)
- counts (requirements by category, scenarios ready vs provisional, questions, gaps)
- the three to five most important findings, usually the root questions and the riskiest vague NFRs
- any pages or diagrams that couldn't be read
- which external regimes you assumed, noting that external checklists are prompts, not legal advice

Don't paste the whole report into chat.

## When to load a reference

Load a file only when its trigger applies. Most documents need one or two of these, not all.

| Load | When |
|---|---|
| `references/nfr-security.md` | The document involves sign-in, roles, personal or financial data, an internet-facing service, integrations or uploads, or any security wording. Gives cue words, a 12-point gap checklist, questions and scenario patterns. |
| `references/nfr-performance.md` | The document mentions speed, load, concurrent users, uptime, recovery, batch windows or scaling. Gives the measurement template and resilience patterns. |
| `references/nfr-data.md` | The document involves personal data, retention or deletion, imports or migration, reporting, audit or backups. Covers choosing the privacy regime. |
| `references/nfr-other.md` | The document stresses reliability, operability, testability, usability, accessibility, compatibility or safety. |
| `references/method.md` | A requirement's `kind`, priority or measurability is hard to call, the ambiguity pass needs more heuristics, or you need the full question bank. |
| `references/scenarios.md` | Writing security, performance or data scenarios, or unsure of the format, range, depth or Gherkin style for a scenario. |
| `references/schema.md` | The build reports an error you can't fix from step 8, or you need the full list of allowed values. |
| `references/example-analysis.json` | You want a complete, valid analysis.json to copy the shape from. |
| `references/sources.md` | You need an abbreviation not listed above, a citation not given elsewhere, or an exact quote from a book. |

## Scope variations
- **"Just the NFRs"**: still list functions, since NFRs attach to them, but draft scenarios only for non-functional requirements.
- **Requirements register (xlsx) input**: each row is usually one requirement. Keep its ID and columns in `source_ref` and `text`. Still split rows that hide two requirements, e.g. a function plus its constraint (LBR ch 9: split "feature + constraint").
- **User asks for Gherkin files**: after the build, write `.feature` files from the `gherkin` scenarios, grouped by `Rule:`. Keep measurement, checklist and charter items in the report.
- **Follow-up with answers**: when the user supplies answers, update analysis.json (answers in questions, provisional → ready, measures filled in) and rebuild. Don't start again from scratch.
