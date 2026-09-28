# analysis.json schema

`scripts/build_outputs.py` validates this before writing anything. `example-analysis.json` in this folder is a complete valid example; copy its shape.

```
document      {title, source_file, analysed_on (YYYY-MM-DD), scope_note?}
functions[]   {id "F-01", name, visibility, source_ref}
requirements[]{id "R-001", text (verbatim or near-verbatim), source_ref (locator from source.md),
               kind, category, applies_to [F-ids | "product-wide"], priority, origin, measurable (bool),
               measure? {scale, meter, benchmark, constraint, target, warning?, tail?},
               ambiguities? [{phrase, readings[], heuristic}], question_ids? [], basis? []}
questions[]   {id "Q-01", question, why, ask (role), level, blocks [R-/S-ids]}
scenarios[]   {id "S-001", title, req_ids [], category, format, range, status, layer, risk, basis [],
               assumptions? [{text, question_id}],
               gherkin:     given [], when, then []
               measurement: measurement {metric, load_profile, environment, threshold, warning?, oracle}
               checklist/charter: items []}
gaps[]        {category, missing, why_it_matters, basis [], question_id?}
```

## Allowed values
| Field | Values |
|---|---|
| kind | function, attribute, constraint, preference, expectation, imposition, assumption |
| category | functional, security, performance, data, reliability, usability, compatibility, maintainability, portability, safety, operability, other |
| priority | must, want, ignore, unconfirmed |
| origin | stated (in the document), implied (necessary consequence of a stated requirement — say which) |
| visibility | evident, hidden, opaque, translucent, frill |
| format | gherkin, measurement, checklist, charter |
| range | normal, abnormal-reasonable, abnormal-unreasonable |
| status | ready, provisional |
| layer | pre-release, pipeline, production |
| risk | high, medium, low |
| level (question) | root, branch, twig |

## Conventions
- `source_ref` is the locator in square brackets from `source.md` (e.g. `p12`, `3.1 Audit ¶14`, `NFRs!R7`). If the document has its own requirement IDs, put them first: `NFR-12 (NFRs!R7)`.
- `basis` entries start with `LIB:` (abbreviation from `sources.md` + chapter) or `EXT:` (standard + section/topic).
- Gaps are not requirements. Never add a requirement with `origin: stated` that the document doesn't contain.
- IDs are unique across functions, requirements, questions and scenarios.

## Validation
Errors (block output): duplicate IDs, unknown references, bad enum values, scenarios tracing to nothing, missing text/source_ref.
Warnings (listed in the report's Validation notes): requirement with no scenario; NFR not measurable and no question; NFR not attached to a function; provisional scenario without assumptions; "or" in a Gherkin step; > 6 steps; measurement without metric/threshold/load_profile/oracle; scenario without basis.
