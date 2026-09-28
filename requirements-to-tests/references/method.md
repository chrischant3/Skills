# Method: classifying requirements, finding ambiguity, making them measurable

Source abbreviations are defined in `sources.md`. `LIB` = the user's library, `EXT` = external standard.

## Contents
1. Classify: functions, attributes, constraints, preferences, expectations
2. Where "non-functional" fits (and where it does not)
3. Ambiguity heuristics to apply to the text
4. Making an attribute measurable
5. Question bank
6. Decisions: choice, assumption, imposition

---

## 1. Classify (ER2 Part IV)

Gause & Weinberg work in a fixed order: **functions → attributes → constraints → preferences → expectations**.

| Kind | Definition | Test |
|---|---|---|
| **function** | "The 'what' of a product… verbs, representing actions for which the product is the subject." (ER2 ch 14) | "The product should ⟨it⟩" reads as a sentence. "should record the event" ✓; "should secure" ✗ |
| **attribute** | "Characteristics desired by the client… adjectives or adverbs." (ER2 ch 15) | Describes *how* a function is done: fast, secure, reliable, tamper-proof |
| **constraint** | "A mandatory condition placed on an M attribute" that can be decided objectively (ER2 ch 16) | Has a yes/no check. "p95 < 2 s at 400 users" |
| **preference** | "A desirable but optional condition placed on an attribute" (ER2 ch 17) | "as fast as possible", "minimise", "better if" |
| **expectation** | What users expect beyond what is written (ER2 ch 18) | Usually unstated. Find it by asking, and state its limits with their source |
| **imposition** | Forced on the project by law, standard, custom or authority (ER2 ch 24) | Names a regulation, policy or standard. Record the source, because it shows when the item can be challenged |
| **assumption** | A decision made "by default, through bias, error, or lack of information" (ER2 ch 24) | Stated assumptions in the document ("hackers will be ignored"). Challenge them |

**Function visibility** (ER2 14.3): *evident* (users see it), *hidden* (users should not notice it; omissions hide here), *opaque* (some groups must not know it exists, e.g. fraud checks and intrusion detection), *translucent*, *frill* (only if free). Name hidden and opaque functions explicitly, because "But I assumed it would…" comes from these.

**Priority: must / want / ignore** (ER2 15.4). Record the document's own wording. Use `unconfirmed` when the document does not say, or when a number is given without saying how firm it is: "Nothing about an attribute itself tells us whether it is a constraint or a preference… Only the strength of the client's fears or desires determines which" (ER2 17.3). Do not treat "shall" as proof of a constraint. If it matters for testing (pass/fail versus ranking), raise a question.

## 2. Where "non-functional" fits

Gause & Weinberg never use the phrase. Their scheme maps onto it like this:

- Most NFRs (performance, reliability, security qualities, usability) are **attributes**. Measurable NFR thresholds are **constraints**. "As fast as possible" NFRs are **preferences**. Laws and standards (GDPR, PCI-DSS) are **impositions**.
- **No free-floating NFRs.** "An attribute does not stand alone, but is rather a modifier of one or more functions" (ER2 15.3). Rewrite "The system shall be secure" as `Security of ⟨function⟩ = (details…)` for each function concerned. Use `product-wide` only for truly global attributes: cost, safety, and product-level regulatory impositions. Where a statement names no function, report that as a finding. Attaching the attribute to a function brings out details: one "reliability" became three different lists for three functions (ER2 15.3).
- **Many "security" and "data" items are really functions.** Examples are "log unauthorised attempts", "notify security", "delete data after 30 days" and "export my data". Run the "The product should…" test before labelling anything non-functional. A hidden function still gets scenarios like any other function. In the analysis these are `kind: function` with `category: security` or `category: data`.
- **The split that decides testability is constraint versus preference**, not functional versus non-functional. A constraint gets a pass/fail oracle. A preference gets a measurement and a report.

Set `category` for every requirement (`functional`, `security`, `performance`, `data`, `reliability`, `usability`, …) so the user's focus areas can be filtered. Set `kind` separately using the table above.

## 3. Ambiguity heuristics

"The fundamental problem of requirements definition is ambiguity" (ER1 ch 9). Apply these to every NFR and every high-risk function. Record each hit as an `ambiguity` with the phrase, the competing readings and the heuristic that exposed it.

1. **Surface checklist** (ER1 2.1):
   - *Comparatives*: fast, small, high, low, secure, robust, scalable, timely, "user-friendly", "appropriate".
   - *Collective nouns*: users, staff, data, records, logs. Which ones?
   - *Hidden-limitation words* (ER2 18.1.2): participating, applicable, where possible, standard, normal, typical.
   - *Optimisation words* (ER2 14.3): minimise, maximise, as … as possible. These are unconstrained preferences; ask for a floor and a ceiling.
   - *Lullaby words* (PS ch 16): "it works", "no problem", "standard security".
   - *Introduced elements*: check that every noun in your reading appears in the source text.
2. **"Mary had a little lamb"** (ER1 9.3): read the sentence stressing each word in turn and write down each reading. "*Users* must be able to delete *their* data *immediately*" gives: which users (patients? admins? deleted accounts?), whose data (created by them, or about them?), and immediately (UI response, or purged from backups?).
3. **"Mary conned the trader"** (ER1 9.4): list every plausible meaning of each key word (secure, available, real-time, delete, record, backup, personal data, response, user, load) and combine them. Each combination is a candidate reading.
4. **Simulated ambiguity poll** (ER1 ch 3–4, ER2 ch 19): for each high-risk requirement, answer a numeric question independently from four to six personas: developer, tester, operator, attacker, auditor, end user. Examples: "how many concurrent users?", "how long until data is gone?", "how many roles?". A wide spread between readings shows ambiguity. Name the phrase that caused each cluster: "What part of the problem statement led you to those inferences?"
5. **Rule of Three** (ARYLO ch 7): "If you can't think of at least three things that might be wrong with your understanding of the problem, you don't understand the problem." Aim for three candidate misreadings on high-risk requirements.
6. **Solutions posing as requirements** (ER2 14.2.4; ARYLO ch 5): "use AES-256", "use Redis cache". Ask what function or attribute each one serves. Record it as an imposition if someone with authority insists on it.
7. **Decision-tree order** (ER1 ch 4): put ambiguities in order of how close they are to the root. Is this a public internet system or an internal one? That decides the whole security posture. Ask root questions first.

Don't resolve ambiguity by picking a reading silently. "Report what you thought they wanted, what you found, and list the discrepancies… Is this acceptable?" (PS ch 12). The skill drafts a scenario under a stated assumption and links it to the question.

## 4. Making an attribute measurable

For every NFR, fill in Gilb's fields (IMPACT; LBR ch 9 uses the first three):

| Field | Meaning |
|---|---|
| **scale** | What is measured, with units (seconds from Confirm to confirmation; % of requests; days until purge) |
| **meter** | How it is measured: tool, protocol, sample, conditions |
| **benchmark** | Current value, or a competitor's |
| **constraint** | Minimum acceptable (fail below this) |
| **target** | Desired value |

Optional: **warning**, an early-warning threshold (LBR: pass at 1 s, a separate test fails at 0.8 s), and **tail**, a maximum or high-percentile bound.

Rules:
- **Always ask for the tail as well as the percentile.** Users agreed to "90% under 1 s" and assumed the rest would stay under 30 s. They got 10-minute waits (ER2 ch 21).
- **State the conditions**: load, data volume, time of day, degraded mode. A number with no conditions is not testable.
- **Define terms** so no argument is possible (ER2 16: define "experienced rider", "average").
- **Constraints can depend on each other** (ER2 16.4): "…errors < 0.9 unless access time < 0.2 s".
- **Probe the boundary** (ER2 16.3): "Would a result just outside this be acceptable?" If yes, the constraint is too strict. "Would one just inside be acceptable?" If no, it is too weak.
- **"Where does that number come from?"** The November 1 "deadline" turned out to be a mild preference.
- **If nobody can agree a metric**, name a person or body with authority to decide, e.g. "accepted by the external pen-test firm" or "signed off by the DPO". That still counts as measurable.
- **Mark don't-care conditions explicitly** (ER2 22.2.3): "not necessarily" leaves designers free.
- If the document gives no number, set `measurable: false`, raise a question, and draft a **provisional** scenario with a clearly assumed threshold. Don't invent a number and present it as the requirement.

## 5. Question bank

Write questions so the answer validates itself: ask what, which and how, not yes/no (RSAD Part IV). "What characters can appear in a card number?" rather than "Are there special characters?" (65% of real cards had them). Ask for **typical and untypical data samples**. Each question records who should answer it and what it blocks.

**Context-free** (ER1 ch 6): What problems does this product solve? What problems could it create? What environment will it meet? What precision is required? Who is the client? What is a highly successful solution worth?

**Loser groups** (ER1 7.1.5): Who must the system be deliberately *unfriendly* to? What must they be prevented from doing or learning? Unauthorised users are users with requirements of their own.

**What happens instead?** (FIFTY): for every "must not", ask what observable thing happens: a rejection message, an audit record, an alert, lockout, or a manual queue. This often uncovers hidden audit and security functions.

**Always / never** (FIFTY): What must always be true? What must never happen? Then design scenarios that try to break each answer.

**Trust boundaries** (FIFTY): How far do we trust data from other systems and third parties: duplicates, missing IDs, invalid values? The answer decides whether defensive-validation scenarios are in scope.

**Expectations** (ER2 18): What are you most looking forward to? Which part will be most valuable to you? (Unstated NFRs come out here.)

**Existing product** (ER2 23): What does the current system do that isn't written down? What goes wrong with it now? Which requirements were implemented once and then removed?

**Metaquestions** (ER1 6.4): Are you the right person to answer? Is there anyone else I should ask? What should I be asking you that I haven't?

## 6. Decisions: choice, assumption, imposition (ER2 ch 24)

Tag stated reasons where the document gives them. "Every requirement should be traceable to its source." Assumptions stated in the document ("the system will be used only on the internal network", "hackers will be ignored") get `kind: assumption`. Where they carry security or data risk, they get a challenging question and a scenario that tests what happens if the assumption is false.
