# Drafting test scenarios from requirements

## Contents
1. The "What if…" pass (ER2 ch 22)
2. Examples and counter-examples (DISC, FIFTY)
3. Failure and extension conditions (Cockburn)
4. Choosing a format: gherkin, measurement, checklist, charter
5. Writing rules (BRIEF and strict Given/When/Then)
6. Risk, layer and depth
7. Provisional scenarios

---

## 1. The "What if…" pass (ER2 ch 22)

The product doesn't exist yet, so treat it as the ultimate black box.

1. For each function, imagine the product is built and ask **"What if…"**.
2. Cover the **range** of use for every function: `normal`, `abnormal-reasonable` and `abnormal-unreasonable`. For Superchalk that was writing on a board, drawing on clothes, and eating it. "No single failure of requirements work leads to more lawsuits than the confident declaration, 'No sane person would do that!'"
3. Answer each case as **"If X happens, the product should do Y"**. Where the document doesn't give Y, the scenario is provisional (see §7).
4. Iterate. Each answer raises new what-ifs; number them hierarchically and stop when the list stops growing.
5. Review for over-constraint: "Does this inadvertently specify more than we really mean?" Mark don't-care conditions.
6. Ask "Does it *not* do what we don't want?" (PS ch 1). This is the source of negative, security and data-leak scenarios.

The elevator security case is a model with four parts (ER2 22.2.1 #3): an unauthorised person attempts a restricted command → the command is **denied**, the event is **logged** (what, when, who if possible), the person is **notified**, and the protected asset includes personal data and configuration.

The elevator power-failure case is also a model (ER2 22.2.1 #5 plus ch 24): **failure** → **degraded-mode behaviour** → **duration** ("at least four hours") → **who is told**.

## 2. Examples and counter-examples

1. Break each requirement into **rules**: one aspect of behaviour each (DISC 2.5).
2. For each rule, write a **key example** with concrete data: outcome first, then action, then context (DISC 3.1). Include only data that matters to the rule.
3. **Counter-examples by smallest change** (FIFTY): mark the inputs and outputs. For each different output value, write the example that produces it by changing *one* input. Keep going until every output appears.
4. **Boundaries, not formulas**: turn every range or threshold into concrete values on each side. For "lock after 5 failures": 4 → not locked, 5 → locked; a success after 4 → counter reset? For "retain 7 years": the day before, the day of, and the day after expiry. Ask about time zones, inclusive or exclusive ends, and date versus datetime.
5. **Invalid inputs: partition by output** (FIFTY). Each distinct rejection message, audit record or alert is its own case, so an error in one field can't hide a broken check in another.
6. **Expect the examples to change the rule.** When writing examples shows the rule is wrong or incomplete, record it as an ambiguity and a question rather than quietly fixing it.
7. Stop at shared understanding. Aim for 3–7 key scenarios per rule, not exhaustive combinations (DISC 3.4).

## 3. Failure and extension conditions (Cockburn)

- "Write every sentence as though it will succeed" (UNIFY 12). Then, for each step, list how it could fail or vary.
- **List every condition first and work out the handling later** (MINI 3.2). Draw a line around the system, list each actor and external system, and brainstorm the failures on every side of that line.
- Look for **failures within failures**: recovery that fails, a timeout during a retry, a power loss during autosave.
- Extensions are where permissions (security), data integrity and resilience requirements come to the surface: `*a. power failure during capture → autosave` is a durability NFR.
- Each extension condition becomes a candidate scenario: `Given ⟨state⟩ / When ⟨step fails⟩ / Then ⟨handling⟩`.

Also walk the **"shaded figs"** emotional paths (FIFTY "Tap into your emotions"):
- **delinquent**: security (authentication, authorisation, permissions, confidentiality)
- **desolate**: empty or null data, zero records
- **forgetful**: resources exhausted, data lost
- **indecisive**: rapid changes of mind, state integrity
- **greedy** and **stressful**: volume and load
- **scary**, **angry** and **embarrassing**: user-facing failures

## 4. Choosing a format

| Format | Use when | Required fields |
|---|---|---|
| `gherkin` | A behavioural rule with a concrete trigger: lockout after N failures, deny and audit, a retention purge on day N, a consent check, a timeout message | `given[]`, `when`, `then[]` |
| `measurement` | A quantitative NFR: latency, throughput, capacity, availability, RPO/RTO, migration duration | `measurement{metric, load_profile, environment, threshold, warning?, oracle}` |
| `checklist` | A cross-cutting concern with no single trigger (hardening, logging hygiene, secure headers). Use 5–9 risk items in Do-Confirm style, naming *risks*, not steps (FIFTY) | `items[]` |
| `charter` | Exploratory testing where the oracle is judgement: "Explore ⟨target⟩ with ⟨resources⟩ to discover ⟨information⟩". Use for capabilities, abuse cases, data lifecycle | `items[]` (one charter per item) |

Security and data rules that describe behaviour fit Gherkin well. Performance usually needs `measurement`. Don't force load profiles into Given/When/Then.

**Measurement scenario template** (LBR ch 9, ER2 ch 16/21, DOH ch 10, Clokie):
- *metric*: unit + tool.
- *load_profile*: operation mix, concurrency, ramp, duration or soak, and **data volume at production scale** ("100s of GB, not 100s of MB", DOH ch 12).
- *environment*: where it runs, and how that differs from production (TGST 4.1).
- *threshold*: a percentile **and** a tail or max ("p95 < 2 s AND max < 10 s").
- *warning*: the early-warning level.
- *oracle*: threshold comparison, regression against the previous run (DOH: fail on > 2% drift), reconciliation counts (data), scanner diff against a baseline (security), or alert fired and cleared (monitoring).

## 5. Writing rules (FORM ch 2–3, FIFTY)

BRIEF: **B**usiness language · **R**eal data only where it reveals intent · **I**ntention-revealing (what, not how: no clicks, URLs or page reloads) · **E**ssential steps only · **F**ocused on one rule · **B**rief (≤ 5 steps).

- Strict order: Given → When → Then. **One When.** If you can't choose between two actions, one of them is context.
- Given declares state, not how the system got there. Given and Then describe values; When is the active action.
- **Never "or" in a step**, because it makes the scenario non-deterministic. An "and" inside a step usually means two rules; split it.
- Titles: hierarchical and searchable, with no conjunctions. Example: "Sign-in - fifth consecutive failure locks the account". Avoid generic words like "basic" and "negative".
- Keep business checks and technical checks apart. If a failure needs a programmer to resolve it (retry policy, message format), it belongs in technical tests, not a business scenario.
- Add a **benefit test** where it helps: "how would you know if it actually works well?" (FIFTY), e.g. "a clinician can find a patient's last three bookings in under 10 s".
- A scenario should name the decision it informs where that isn't obvious. "To qualify as a test, an action has to seek information that will influence action" (PS ch 10).

## 6. Risk, layer and depth

- **risk** (`high` / `medium` / `low`): likelihood × consequence (PS ch 1). Aim for the most depth where both are high. Security, personal-data and money-moving functions are rarely low.
- **layer**: `pre-release` (a test in an environment), `pipeline` (automated on every build) or `production` (a monitor, a synthetic transaction or an alert). Clokie's hourglass: for every NFR, consider **one pre-release check and one production monitor**. Availability and security telemetry often only make sense in production.
- Testing is sampling ("Testing is, at best, sampling", PS ch 3). A diverse sample beats a large one. For security, add review-based verification as well as tests: the password backdoor that survived a strict test plan was found by a code review.
- Target depth: every non-ignored requirement gets at least one scenario. Each security, performance or data requirement gets its boundary or counter-examples plus at least one abnormal-unreasonable case where one exists. Functional requirements get a key example plus the most informative counter-example.

## 7. Provisional scenarios

The user asked for scenarios drafted now, with assumptions flagged. Where the document leaves Y (the expected outcome) or the threshold open:

- set `status: provisional`
- list each assumption in `assumptions[]`, linked to the question that would settle it
- choose assumptions a reasonable stakeholder could accept, and say where they come from ("assumed p95 < 2 s, the common web norm; not in the document")
- keep the provisional value obviously provisional in the text, so nobody runs it as agreed acceptance criteria.
