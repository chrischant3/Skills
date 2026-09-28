# Other quality attributes (brief)

Use ISO/IEC 25010 as the classification backbone [EXT; the 2023 revision's characteristics are functional suitability, performance efficiency, compatibility, interaction capability (formerly usability), reliability, security, maintainability, flexibility (formerly portability) and safety]. Map them to the analysis `category` values: reliability → `reliability`; interaction capability → `usability`; flexibility → `portability`; the rest by name; operational concerns → `operability`.

The library emphasises these; give them lighter treatment than security/performance/data unless the document stresses them.

- **Reliability** — error rates differ by function and depend on whether users can recover ("misinformation no more than once in a hundred… as long as people could recover"; safety functions < 1 in 10,000) [LIB ER1 6.3]. Monitoring components need their own reliability and false-alarm limits [LIB ER2 18.2.2 #8]. Error correction is a forgotten function [LIB ER2 23.2.2].
- **Operability / observability** — codified NFR checklist: telemetry, dependency tracking, graceful degradation, forward/backward compatibility, data archiving, searchable logs, request tracing, central runtime config/feature flags [LIB DOH ch 20]. Test monitors by causing the condition they should detect; an alert with no clear response is a failed monitor [LIB Clokie]. Logs must let support reach the same diagnosis [LIB Clokie; DOH ch 14].
- **Testability** — controllability (set state, stub dependencies, control log level) and observability are requirements in their own right: "these features are what turns functionality into a product" [LIB TGST]. Flag when the document makes an NFR untestable in practice (no perf environment, no way to set data state).
- **Usability / accessibility** — measurable form: assistance requests per user, time per task, error rate on a defined sample of defined users [LIB ER2 ch 16 elevator example]; satisfaction survey as a constraint [LIB ER2 ch 21]. Accessibility conformance → WCAG 2.2 AA [EXT].
- **Compatibility** — declared browsers/OS/devices; interaction with other software [LIB CET › Execution Environment].
- **Safety** — "someone could die" outranks everything [LIB PS ch 13]; hazardous-condition requirements use "not necessarily… but hazardous conditions will be avoided" don't-care phrasing [LIB ER2 22.2.3].
