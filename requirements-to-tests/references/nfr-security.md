# Security requirements: cues, gaps, questions, scenario patterns

Tags: `LIB` = the user's library (see `sources.md`); `EXT` = external standard. The library has no dedicated security book: it covers the *method* (loser groups, "what happens instead", bad paths, telemetry) and the checklist content comes from OWASP. Cite OWASP ASVS by **chapter name** (e.g. "ASVS Authentication"), not by number; chapter numbering changed between ASVS 4.0 and 5.0.

## Cues in the document
- Sign-in, password, MFA, SSO, session, token, API key, role, permission, "only X can", admin, approval, delegation.
- Personal data, payment/card, health, children, financial records (also read `nfr-data.md`).
- Free-text fields, file upload, import, search, URLs from users, webhooks, integrations → injection / SSRF / file-handling risk. "If the application crashes, there is usually a connection to security" (LIB CET › Versatile Data).
- Audit, log, monitor, alert, fraud, rate limit, bot, abuse (LIB DOH ch 22).
- Encryption, TLS, certificates, key length, "secure", "hardened", "compliant with ⟨standard⟩".
- Third-party or open-source components, deployment pipeline, cloud config (LIB DOH ch 22 › supply chain, pipeline).
- Stated assumptions: "internal network only", "trusted users", "hackers will be ignored" (LIB ER2 24.1.2 #21) → challenge.

## Gap checklist (raise as `gaps` + questions when relevant and absent)
Only list gaps that plausibly apply to this product; say why.
1. **Authentication**: how users prove identity; MFA for privileged roles; password/credential policy; account recovery; lockout/throttling. [EXT ASVS Authentication; NCSC password guidance]
2. **Session management**: timeout (idle/absolute), logout invalidation, concurrent sessions. [EXT ASVS Session Management]
3. **Authorisation**: role model; who may see/change *other people's* records (object-level access / IDOR); admin separation; least privilege. [LIB ER1 7.1.5 loser groups; EXT ASVS Authorization]
4. **Input handling**: validation, output encoding, injection, file upload limits and types. [LIB DOH ch 22; EXT ASVS Validation / Encoding; OWASP Top 10 Injection]
5. **Cryptography & transport**: TLS for all traffic; encryption at rest for sensitive data; key management. [EXT ASVS Cryptography / Secure Communication]
6. **Security logging & alerting**: which events are logged (sign-in success/failure, password reset, privilege change, data export), log protection, alert thresholds, who responds. [LIB DOH ch 14, ch 22 › Creating Security Telemetry]
7. **Errors**: no stack traces/secrets in responses. [EXT ASVS Security Logging and Error Handling]
8. **Abuse & rate limiting**: brute force, enumeration, scraping, double submission. [LIB DOH ch 22]
9. **Dependencies & supply chain**: known-vulnerability scanning; pipeline credentials. [LIB DOH ch 22]
10. **Configuration hardening**: known-good baseline, drift detection. [LIB DOH ch 22]
11. **Opaque functions**: must any control or outage be invisible to attackers? [LIB ER2 14.3]
12. **Verification method**: pen test, code review, threat model — testing alone cannot prove absence (the backdoor that survived a strict test plan for 3 years; LIB PS ch 3).

## Questions
- Who must the system be *unfriendly* to, and what must they not do or learn? [LIB ER1 7.1.5]
- For each rejected action: what happens instead — message, audit record, alert, lockout? [LIB FIFTY]
- Which security events must be logged, which alert, who responds, within what time? [LIB DOH ch 22]
- What does "secure" mean measurably? e.g. "withstand a DDoS for thirty minutes" (LIB LBR ch 9), "no High/Critical findings in the external pen test", "ASVS Level 2".
- Which ASVS level (1 opportunistic / 2 standard / 3 high-assurance) fits this product? [EXT ASVS]
- Can one user ever see another user's data? Under what roles? [EXT ASVS Authorization]
- How will auditors get evidence — on demand from telemetry, or samples? [LIB DOH ch 23]

## Scenario patterns
| Pattern | Format | Oracle | Basis |
|---|---|---|---|
| Unauthorised action → deny + log (who/what/when) + notify | gherkin | Action not performed; audit event present with fields | LIB ER2 22.2.1 #3 |
| Lockout / throttle boundary: N-1, N, success resets? , after lockout window | gherkin (outline) | Locked exactly at N; event logged | LIB FIFTY boundaries; EXT ASVS Authentication |
| Object-level access: user A requests user B's record by ID | gherkin | Refused (no data leak, no existence leak) | EXT OWASP Top 10 Broken Access Control |
| Role matrix: each role × each sensitive function | gherkin outline / checklist | Allowed/denied matches matrix | EXT ASVS Authorization |
| Session: idle timeout, logout invalidates token, reuse old token | gherkin | Token rejected | EXT ASVS Session Management |
| Injection & naughty strings on every free-text/upload input | checklist + automation | Input rejected or escaped; zero DB syntax errors | LIB DOH ch 22; LIB CET; Clokie › Automation |
| Security telemetry: synthetic brute force triggers alert; failed/successful sign-in ratio visible | measurement / production | Alert fires within agreed time; routed; clears | LIB DOH ch 22; Clokie › Testing monitoring |
| Error responses leak nothing (stack traces, versions, secrets) | checklist | No sensitive detail | EXT ASVS Error Handling |
| Dependency and static/dynamic scan in pipeline | checklist (pipeline) | No findings above agreed severity; diff vs baseline | LIB DOH ch 22 |
| Hardening baseline: open ports, TLS config, headers | checklist | Matches baseline | LIB DOH ch 10/22 |
| Abuse-case charter: "Explore ⟨function⟩ as a malicious user to discover how to subvert ⟨control⟩" | charter | Session notes | LIB Clokie › Exploration; ER2 22.4 misuse |
| Opaque function: attacker cannot tell control/outage state | gherkin/charter | Responses indistinguishable | LIB ER2 14.3 |
