# Performance, capacity and availability: cues, gaps, questions, scenario patterns

Tags: `LIB` = the user's library; `EXT` = external practice. Library coverage is good on method (Gilb quantification, tails, pipeline regression, production-scale data, monitoring as testing); it has no performance-engineering or SRE book, so workload modelling and SLO vocabulary are EXT.

## Cues in the document
- Time words: within, fast, responsive, real-time, near-real-time, instant, overnight, **batch window**, "before business opens" (LIB LBR ch 9: the payments batch unfinished when the bank opened — an unstated time window).
- Volume words: users, concurrent, peak, transactions per second, records, file size, "grow to", seasonal peaks, campaigns.
- Availability words: uptime, SLA, 24/7, "five nines", failover, redundancy, DR, maintenance window.
- High-value operations named in the doc (search, checkout, booking, report) — each needs its own target (LIB FIFTY "Quantify…"; DOH ch 10).
- Elasticity / auto-scaling claims (LIB Clokie › Cloud).
- New broadcast-style functions (notify all, bulk export) — "leaked functions" create load (LIB ER2 23.2.4); capacity creates its own demand (turnpike effect, ER2 24.2.3).

## Gap checklist
1. **Response time per key operation**, with percentile **and** tail/max. [LIB ER2 ch 21; LBR ch 9]
2. **Load profile**: peak concurrency, operation mix, growth over N years, data volume. [LIB DOH ch 10/12; FIFTY]
3. **Throughput / batch window**: jobs that must finish by a time. [LIB LBR ch 9]
4. **Availability target** and measurement window; planned maintenance. [LIB Clokie › Monitoring as testing; EXT SLO/SLI practice]
5. **Degradation**: behaviour when a dependency is slow/down; graceful degradation; timeouts. [LIB DOH ch 20]
6. **Recovery**: RTO (time to restore service) and RPO (data loss tolerated). [EXT ISO 22301 / ITIL terminology — library never defines these]
7. **Scalability**: headroom required; what happens beyond capacity (queue, reject, degrade). [LIB DOH ch 10]
8. **Where it is measured**: test environment similarity to production; production monitoring. [LIB TGST 4.1; Clokie hourglass]
9. **Stated load assumptions** and what would invalidate them (correlated demand — the FDR phone-call story). [LIB ER2 24.2.2]

## Questions
- For ⟨operation⟩: what unit and tool, current value, minimum acceptable, target? [LIB LBR ch 9 / IMPACT Gilb]
- What percentage of requests must meet it, and what is the worst acceptable for the rest? [LIB ER2 ch 21]
- Under what load: concurrent users, mix, data volume, time of day? Is there a seasonal/event peak?
- How much better is 2 s than 4 s to you — is this a pass/fail constraint or a preference? [LIB ER2 ch 17; LBR]
- Where does this number come from? [LIB ER2 16.6.2]
- What happens when the limit is exceeded — queue, reject with message, degrade? [LIB DOH ch 20]
- How long may the service be unavailable, and how much recent data may be lost after a failure? (RTO/RPO) [EXT]
- Is a production-like performance environment available, and at production data volume? [LIB TGST 4.1; DOH ch 12]

## Scenario patterns
All `format: measurement` unless noted.
| Pattern | Threshold/oracle form | Basis |
|---|---|---|
| Key-operation latency at peak profile | pXX < t AND max < T; warning at 0.8·t | LIB LBR ch 9; ER2 ch 21 |
| Regression per build vs baseline | fail if drift > N% (DOH example 2%) | LIB DOH ch 10 |
| Load from parallelised acceptance tests (search/checkout) | latency & error rate at stated concurrency | LIB DOH ch 10 |
| Data-volume growth: response time vs record count (missing index 100 ms → 30 s) | ~linear; DB calls per request stable | LIB DOH ch 10 |
| Production-scale data set | tests on "100s of GB, not 100s of MB" | LIB DOH ch 12 |
| Batch within window | completes by deadline with margin, at projected volume | LIB LBR ch 9 |
| Soak / endurance | no degradation or memory growth over N hours | LIB DOH ch 10; TGST 4.3 |
| Stress beyond capacity | defined behaviour (queue/reject/degrade), recovers after | LIB DOH ch 20 |
| Resilience: kill node / stop DB / inject latency / lose a zone (gherkin or charter) | recovers within RTO; user impact within budget | LIB Clokie › Destructive testing; DOH ch 19 |
| Failover and restore drill | service back within RTO; data loss ≤ RPO | LIB Clokie; EXT ISO 22301 |
| Availability via synthetic transactions in production (`layer: production`) | success rate ≥ target over window | LIB Clokie › Monitoring as testing |
| Leading-indicator alerts: latency, disk, memory, healthy nodes (`layer: production`) | alert fires, routes, clears; not noisy | LIB DOH ch 15; Clokie |
| Benefit test: task-level timing with realistic content (charter) | user completes task in agreed time | LIB FIFTY "Test benefit" |

Note: a large functional test count is not a load test, though it can accidentally be one (LIB Weinberg, *How to Observe Software Systems*).
