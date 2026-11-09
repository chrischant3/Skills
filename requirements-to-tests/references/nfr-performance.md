# Performance, capacity and availability: cues, gaps, questions, scenario patterns

Load this when the document mentions speed, load, users at once, uptime, recovery, batch windows or scaling.

Tags: `BOOK` = a published book (see `sources.md`); `EXT` = external practice. The books cover method well (Gilb quantification, tails, pipeline regression, production-scale data, monitoring as testing); none is a performance-engineering or SRE text, so workload modelling and SLO vocabulary are EXT.

## Cues in the document
- Time words: within, fast, responsive, real-time, near-real-time, instant, overnight, **batch window**, "before business opens" (BOOK LBR ch 9: the payments batch unfinished when the bank opened — an unstated time window).
- Volume words: users, concurrent, peak, transactions per second, records, file size, "grow to", seasonal peaks, campaigns.
- Availability words: uptime, SLA, 24/7, "five nines", failover, redundancy, DR, maintenance window.
- High-value operations named in the doc (search, checkout, booking, report) — each needs its own target (BOOK FIFTY "Quantify…"; DOH ch 10).
- Elasticity / auto-scaling claims (BOOK Clokie › Cloud).
- New broadcast-style functions (notify all, bulk export) — "leaked functions" create load (BOOK ER2 23.2.4); capacity creates its own demand (turnpike effect, ER2 24.2.3).

## Gap checklist
1. **Response time per key operation**, with percentile **and** tail/max. [BOOK ER2 ch 21; LBR ch 9]
2. **Load profile**: peak concurrency, operation mix, growth over N years, data volume. [BOOK DOH ch 10/12; FIFTY]
3. **Throughput / batch window**: jobs that must finish by a time. [BOOK LBR ch 9]
4. **Availability target** and measurement window; planned maintenance. [BOOK Clokie › Monitoring as testing; EXT SLO/SLI practice]
5. **Degradation**: behaviour when a dependency is slow/down; graceful degradation; timeouts. [BOOK DOH ch 20]
6. **Recovery**: RTO (time to restore service) and RPO (data loss tolerated). [EXT ISO 22301 / ITIL terminology — library never defines these]
7. **Scalability**: headroom required; what happens beyond capacity (queue, reject, degrade). [BOOK DOH ch 10]
8. **Where it is measured**: test environment similarity to production; production monitoring. [BOOK TGST 4.1; Clokie hourglass]
9. **Stated load assumptions** and what would invalidate them (correlated demand — the FDR phone-call story). [BOOK ER2 24.2.2]

## Questions
- For ⟨operation⟩: what unit and tool, current value, minimum acceptable, target? [BOOK LBR ch 9 / IMPACT Gilb]
- What percentage of requests must meet it, and what is the worst acceptable for the rest? [BOOK ER2 ch 21]
- Under what load: concurrent users, mix, data volume, time of day? Is there a seasonal/event peak?
- How much better is 2 s than 4 s to you — is this a pass/fail constraint or a preference? [BOOK ER2 ch 17; LBR]
- Where does this number come from? [BOOK ER2 16.6.2]
- What happens when the limit is exceeded — queue, reject with message, degrade? [BOOK DOH ch 20]
- How long may the service be unavailable, and how much recent data may be lost after a failure? (RTO/RPO) [EXT]
- Is a production-like performance environment available, and at production data volume? [BOOK TGST 4.1; DOH ch 12]

## Scenario patterns
All `format: measurement` unless noted.
| Pattern | Threshold/oracle form | Basis |
|---|---|---|
| Key-operation latency at peak profile | pXX < t AND max < T; warning at 0.8·t | BOOK LBR ch 9; ER2 ch 21 |
| Regression per build vs baseline | fail if drift > N% (DOH example 2%) | BOOK DOH ch 10 |
| Load from parallelised acceptance tests (search/checkout) | latency & error rate at stated concurrency | BOOK DOH ch 10 |
| Data-volume growth: response time vs record count (missing index 100 ms → 30 s) | ~linear; DB calls per request stable | BOOK DOH ch 10 |
| Production-scale data set | tests on "100s of GB, not 100s of MB" | BOOK DOH ch 12 |
| Batch within window | completes by deadline with margin, at projected volume | BOOK LBR ch 9 |
| Soak / endurance | no degradation or memory growth over N hours | BOOK DOH ch 10; TGST 4.3 |
| Stress beyond capacity | defined behaviour (queue/reject/degrade), recovers after | BOOK DOH ch 20 |
| Resilience: kill node / stop DB / inject latency / lose a zone (gherkin or charter) | recovers within RTO; user impact within budget | BOOK Clokie › Destructive testing; DOH ch 19 |
| Failover and restore drill | service back within RTO; data loss ≤ RPO | BOOK Clokie; EXT ISO 22301 |
| Availability via synthetic transactions in production (`layer: production`) | success rate ≥ target over window | BOOK Clokie › Monitoring as testing |
| Leading-indicator alerts: latency, disk, memory, healthy nodes (`layer: production`) | alert fires, routes, clears; not noisy | BOOK DOH ch 15; Clokie |
| Benefit test: task-level timing with realistic content (charter) | user completes task in agreed time | BOOK FIFTY "Test benefit" |

Note: a large functional test count is not a load test, though it can accidentally be one (BOOK Weinberg, *How to Observe Software Systems*).
