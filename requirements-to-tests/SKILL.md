---
name: requirements-to-tests
description: >-
  Reads a requirements document (PDF, Word, xlsx/csv register, or text) and produces a traceable
  analysis: requirements extracted and classified, ambiguities exposed, missing requirements raised as
  questions, and test scenarios drafted - with most depth on non-functional requirements: security,
  performance/capacity/availability, and data handling (privacy, retention, integrity, migration,
  backup). Outputs a Markdown report plus an xlsx workbook. Grounded in Gause & Weinberg's Exploring
  Requirements, example mapping/BDD and the user's testing books, with OWASP ASVS, UK GDPR and ISO
  25010 as labelled external checklists. Use whenever the user shares a spec, PRD, SoW, tender/RFP,
  requirements register, story export or NFR list and wants requirements identified, reviewed, made
  testable, or turned into test scenarios, acceptance criteria or a test plan - or asks "what's missing
  from this spec" or "what should we ask the client". Not for unit tests against existing code.
---

# Requirements to test scenarios

Turn a requirements document into four things:
- requirements that can be traced back to the document
- ambiguities made visible
- questions worth asking
- draft test scenarios, deepest for **security, performance and data handling**

This follows Gause & Weinberg: "The fundamental problem of requirements definition is ambiguity". The job is to find the ambiguity and put it in front of people, not to paper over it.

Scripts live in `scripts/` next to this file; call them with the absolute path. References are in `references/`; load them at the steps that name them.

## Principles (why the workflow looks like this)

- **Trace everything.** Every requirement carries a verbatim quote and a locator from the source. Every scenario traces to requirement IDs. The build script refuses to write outputs when traceability is broken.
- **Don't invent requirements.** If you expected something (e.g. an erasure policy) and didn't find it, that is a *gap* and a *question*, not a requirement. A requirement you derived from a stated one gets `origin: implied`, with the reason given.
- **Don't resolve ambiguity silently.** Where the document is vague, draft the scenario anyway (the user wants drafts now), but mark it `provisional`, state the assumption, and link it to the question that would settle it.
- **Attributes modify functions.** An NFR like "the system shall be secure" is not tested in the abstract. Attach it to the functions it qualifies. A security or data statement that is really a verb ("log failed sign-ins", "delete after 30 days") is a hidden function, and gets tested as one.
- **Measurable or asked.** Every NFR either has a measure (scale, meter, constraint, target) or has a question asking for one.
- **Label sources.** `LIB:` for the user's books, `EXT:` for external standards. The library has no dedicated security, performance or privacy book, so checklist content in those areas comes from external standards, and the reader should be able to see that.

## Workflow

### 1. Set up and extract
Default output folder: `<input folder>/<input stem>-requirements/`. Use a different folder if the user names one. Requirements documents are often confidential: keep all processing local, and don't upload them or paste large parts into other tools.

```bash
python3 <skill>/scripts/extract.py "<document>" --out-dir "<out>"
```

This writes `source.md` (one `[locator] text` line per paragraph, table row or spreadsheet row) and `manifest.json`. Read the manifest warnings. Pages with no text are probably scans or diagrams, and requirements often hide in diagrams and tables. Tell the user which pages were skipped, and offer to read them as images. Formats: .pdf, .docx, .xlsx/.xlsm, .csv, .txt/.md; .doc, .rtf and .odt via macOS `textutil`.

Read `source.md` in full. For long documents (more than about 30k words), work through it section by section, keeping a running list. Don't skim.

### 2. Understand the context
Before classifying anything, note:
- what the product is
- who uses it, including who must be kept *out*
- what environment it runs in (public internet? personal data? money?)
- which regimes apply (UK or EU GDPR, PCI DSS, sector rules)

These root answers decide how much security and data depth is warranted. If they're unclear, they become **root** questions. Load `references/method.md` now.

### 3. Functions, then requirements
1. List the **functions** (verbs the product performs), including hidden and opaque ones that only appear in NFR or security sections.
2. Extract **every requirement statement**. Keep the document's own IDs (`NFR-12 (NFRs!R7)`). Classify each one:
   - `kind`: function / attribute / constraint / preference / expectation / imposition / assumption (method.md §1–2)
   - `category`: functional / security / performance / data / reliability / usability / …
   - `applies_to`: function IDs, or `product-wide` only if it genuinely applies everywhere
   - `priority`: must / want / ignore as the document states it; `unconfirmed` if it doesn't
   - `measurable`, plus `measure` fields (Gilb) for every NFR
3. Headings, rationale and examples in the document are not requirements, but they are useful context.

### 4. Ambiguity pass
Apply method.md §3 to every NFR and every high-risk function:
- the surface checklist
- "Mary had a little lamb" stress readings
- key-word meanings
- a simulated ambiguity poll across personas (developer, tester, operator, attacker, auditor, user)

Record each real ambiguity with its competing readings. Keep the list to ambiguities that would change a design or a test.

### 5. Gap pass for the focus areas
Load `references/nfr-security.md`, `references/nfr-performance.md` and `references/nfr-data.md`. Load `references/nfr-other.md` if the document stresses reliability, operability, usability or safety.

Go through each gap checklist. Record a gap only if it plausibly applies to *this* product, and say why. A static brochure site does not need a lockout policy. Each gap gets a question.

### 6. Questions
Write each question so the answer validates itself: ask what, which or how, and ask for typical *and* untypical examples (method.md §5). Each question gets:
- who to ask
- why it matters
- what it blocks
- a level: `root` (changes everything below it), `branch` or `twig`

Merge duplicates. A short, sharp question list is worth more than a long one.

### 7. Draft scenarios
Load `references/scenarios.md`.
- Run the "What if…" pass across normal, abnormal-reasonable and abnormal-unreasonable use.
- Write examples and counter-examples at the boundaries.
- Use Cockburn extensions for failures.
- Pick the right format per scenario: `gherkin` for behavioural rules, `measurement` for quantitative NFRs, `checklist` for cross-cutting risks, `charter` for exploration.
- Depth: every non-ignored requirement gets at least one scenario. Security, performance and data requirements get boundary or counter-examples plus at least one abnormal-unreasonable (abuse or failure) case. For NFRs, consider both a pre-release check and a production monitor.
- Give every scenario a `basis`.

### 8. Build and check
Write `<out>/analysis.json` following `references/schema.md`. `references/example-analysis.json` is a valid example to copy the shape from. Then run:

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
- which external regimes you assumed

Don't paste the whole report into chat.

## Scope variations
- **"Just the NFRs"**: still list functions, since NFRs attach to them, but draft scenarios only for non-functional requirements.
- **Requirements register (xlsx) input**: each row is usually one requirement. Keep its ID and columns in `source_ref` and `text`. Still split rows that hide two requirements, e.g. a function plus its constraint: LBR ch 9 says split "feature + constraint".
- **User asks for Gherkin files**: after the build, write `.feature` files from the `gherkin` scenarios, grouped by `Rule:`. Keep measurement, checklist and charter items in the report.
- **Follow-up with answers**: when the user supplies answers, update analysis.json (answers in questions, provisional → ready, measures filled in) and rebuild. Don't start again from scratch.
