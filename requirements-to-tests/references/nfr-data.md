# Data handling: cues, gaps, questions, scenario patterns

Covers privacy/personal data, retention and deletion, integrity, migration, volume, backup/restore, audit, test data.
Tags: `LIB` = the user's library; `EXT` = external standard. **The library is weakest here**: it gives the operational side (CRUD lifecycle, audit logging, migration patterns, backup/restore drills, production-sized data, test-data hygiene). All privacy-law content is `EXT` — UK GDPR / EU GDPR and ICO guidance (UK GDPR as amended by the Data (Use and Access) Act 2025; check current ICO guidance before relying on detail). Card data → PCI DSS. Say which regime you assumed.

## Cues in the document
- Personal data: names, contact details, identifiers, location, health, biometrics, children, financial, "customer data", "profile", tracking ("identity and travel patterns of all individuals", LIB ER2 18.2.3).
- Consent, opt-in/out, marketing, cookies, analytics, profiling, automated decisions.
- Export, download, delete, anonymise, archive, "keep for N years", retention, purge.
- Import, migration, conversion, cut-over, legacy data, schema change (LIB DOH ch 12; GOATS: "production data is always unstructured").
- Integrations and data from other parties (trust boundaries, LIB FIFTY).
- Backup, restore, DR, replication, "no data loss".
- Audit trail, "who changed what", history, versioning.
- Reporting/analytics that must stay correct (LIB Clokie: tests in production "could be affecting real reporting").

## Gap checklist
1. **Data inventory**: which personal / sensitive data, why (purpose), lawful basis. [EXT UK GDPR Art 5–6]
2. **Minimisation**: only the fields needed for the purpose. [EXT UK GDPR Art 5(1)(c)]
3. **Retention & deletion**: period per record type, what happens at expiry, residual copies (backups, logs, search indexes, exports, caches). [EXT Art 5(1)(e); LIB Clokie › Logging retention]
4. **Data subject rights**: access, rectification, erasure, restriction, portability, objection — which apply and the response time. [EXT UK GDPR Ch III; ICO]
5. **Consent** where it is the basis: capture, record, withdraw. [EXT]
6. **Access control on data** — link to `nfr-security.md` authorisation. [EXT ASVS Data Protection]
7. **Integrity**: validation at trust boundaries; duplicates; referential integrity; error correction as a function (errors arrive from outside — LIB ER2 23.2.2 royalties). [LIB FIFTY trust boundaries]
8. **Audit logging** of data changes and access. [LIB DOH ch 14: "Data changes, such as adding, editing, or deleting data"]
9. **Backup & restore**: frequency, restore tested, RPO. [LIB Clokie › Destructive testing; DOH ch 14 "Backup success/failure"]
10. **Migration**: reconciliation, rollback without lost transactions, old/new versions against one schema. [LIB DOH ch 12]
11. **Volume & growth**: projected record counts, archiving to bound size. [LIB DOH ch 20]
12. **Data in logs & test environments**: no personal data/secrets in logs; masked or synthetic test data; test records invisible to customers and reports. [LIB Clokie › Monitoring-as-testing limitations; EXT OWASP Logging Cheat Sheet]
13. **International transfers / hosting location**, if any third-party or cloud processing. [EXT UK GDPR Ch V]
14. **Breach detection & notification** duties (72 h to regulator). [EXT UK GDPR Art 33]

## Questions
- For each data entity: who creates, reads, updates, deletes it — fully or partially? [LIB CET › Versatile Data]
- How long must each record type be kept, why (source of the rule), and what happens at the end? [LIB ER2 ch 24 impositions; EXT]
- When a user asks for deletion, what must disappear, from where, by when — including backups and logs?
- Which data changes and accesses must be audited, how long are audit logs kept, can archived logs be restored? [LIB DOH ch 14; Clokie]
- How much do we trust data from ⟨upstream⟩ — duplicates, missing IDs, invalid values? Detect, alert, or correct? [LIB FIFTY]
- Can I see some typical and untypical real (anonymised) records? [LIB RSAD self-validating questions]
- For migration: how will we prove nothing was lost or altered (counts, checksums, sampled comparison)? What is the rollback? [LIB DOH ch 12]
- How much data may be lost in a failure (RPO), and when was restore last proven? [EXT]

## Scenario patterns
| Pattern | Format | Oracle | Basis |
|---|---|---|---|
| Retention boundary: record at expiry −1 day / day / +1 day | gherkin outline | Kept / purged exactly per rule | EXT Art 5(1)(e); LIB FIFTY boundaries |
| Erasure request removes data everywhere | gherkin + charter | Absent from DB, search, exports, logs; backups handled per policy | EXT UK GDPR Art 17 |
| Subject access / export produces complete, correct data in stated format and time | gherkin | Content complete; delivered within deadline | EXT UK GDPR Art 15, 20 |
| Consent withdrawn → processing stops | gherkin | No further processing of that purpose | EXT UK GDPR Art 7 |
| CRUD lifecycle incl. partial update/delete and mixed stages | charter | Consistent state; nothing orphaned | LIB CET › Versatile Data |
| Invalid/duplicate upstream data at trust boundary | gherkin outline (partition by output) | Each error class → its own rejection/alert | LIB FIFTY |
| Audit coverage: every create/update/delete/access/privileged change logged with correlation ID | checklist + gherkin | Event present, correct fields | LIB DOH ch 14; Clokie › Testing logging |
| Logs contain no personal data or secrets | checklist | Scan of log output clean | EXT OWASP Logging Cheat Sheet |
| Backup & restore drill | measurement | Restored data matches source (counts/checksums); within RTO; loss ≤ RPO | LIB Clokie; EXT ISO 22301 |
| Archived log/data restore | gherkin | Restores correctly | LIB Clokie › Logging |
| Migration rehearsal at production size | measurement | Completes in window; reconciliation counts and checksums match | LIB DOH ch 12 |
| Expand/contract schema: old and new app on same DB; rollback | gherkin | No errors; no lost transactions | LIB DOH ch 12 |
| Volume growth to projected N years | measurement | Performance within limits; archiving bounds size | LIB DOH ch 10/20 |
| Test data in production invisible to customers and excluded from reports | checklist | Not visible; reports unaffected | LIB Clokie |
| Privacy/fairness of tracking data (who can see travel patterns; no discrimination) | charter | Findings | LIB ER2 18.2.3 #10–11 |
