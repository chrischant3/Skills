# Sources

Load this when you need to expand an abbreviation, add a citation that isn't already given in another reference file, or quote a source directly. You don't need copies of these books: the method is summarised in `SKILL.md` and the other reference files, and every `basis` you need is cited there.

Locators are Book › Chapter › Section. **Don't cite page numbers**: they differ between print, PDF and e-book editions.

## Books (BOOK) — published works on requirements and testing
| Abbrev | Book | Use for |
|---|---|---|
| ER1 | Gause & Weinberg, *Exploring Requirements One: Quality Before Design* | Ambiguity, context-free questions, loser groups |
| ER2 | Gause & Weinberg, *Exploring Requirements Two: First Steps to Design* | Functions/attributes/constraints/preferences/expectations; ambiguity metrics; test cases (ch 22); agreements (ch 24) |
| ARYLO | Gause & Weinberg, *Are Your Lights On?* | Problem definition; Rule of Three |
| RSAD | Weinberg, *Rethinking Systems Analysis and Design* | Self-validating questions |
| PS | Weinberg, *Perfect Software and Other Illusions about Testing* | What testing can/can't tell; sampling; significance |
| LBR | Allan Kelly, *A Little Book about Requirements and User Stories* | NFRs as requests for testing; Gilb's questions (ch 9) |
| DISC | Nagy & Rose, *Discovery: Explore behaviour using examples* | Rules and examples; example mapping |
| FORM | Rose & Nagy, *Formulation: Document examples with Given/When/Then* | BRIEF; strict Given/When/Then |
| FIFTY | Adzic, Evans & Roden, *Fifty Quick Ideas to Improve Your Tests* | Counter-examples, boundaries, risk checklists, shaded figs, trust boundaries, quantify |
| MINI / UNIFY | Cockburn, *The Mini-Book on Use Cases*; *Unifying User Stories, Use Cases, Story Maps* | Extensions as failure scenarios; where NFRs live |
| IMPACT | Adzic, *Impact Mapping* | Gilb scale/meter/benchmark/constraint/target |
| Clokie | Katrina Clokie, *A Practical Guide to Testing in DevOps* | Monitoring as testing, destructive testing, logging, risk workshop, hourglass |
| DOH | Kim et al., *The DevOps Handbook* | Security in pipeline & telemetry (ch 22–23), perf testing (ch 10), data/migrations (ch 12), logging (ch 14), NFR list (ch 20) |
| TGST | Winter & Meaney, *Team Guide to Software Testability* | Testability as an NFR; environments |
| ET / CET | Pyhäjärvi, *Exploratory Testing* / *Contemporary Exploratory Testing* | Data lifecycle; charters; execution environment |
| GOATS | Ottosen, *Goal-Aligned Test Strategies* | Linking tests to goals and risk |

## External (EXT) — standards and regulations, used where the books don't cover the topic
| Standard | Use for |
|---|---|
| ISO/IEC 25010 (2023) | Quality-characteristic taxonomy |
| OWASP ASVS (cite by chapter *name*), OWASP WSTG, OWASP Top 10, OWASP Cheat Sheets | Security requirement checklists and test cases |
| GDPR (EU) / UK GDPR (as amended by the Data (Use and Access) Act 2025) and regulator guidance; or the regime that applies to the product (e.g. CCPA/CPRA, HIPAA, Australia's Privacy Act) | Personal data principles, rights, retention, breach |
| PCI DSS | Card data |
| ISO 22301 / ITIL | RPO, RTO, continuity terms |
| WCAG 2.2 | Accessibility |
| NIST SP 800-63B; national guidance (e.g. UK NCSC) | Password and authentication guidance |

Always tell the reader which external regime you assumed (e.g. EU GDPR, UK GDPR, CCPA) and that external checklists are prompts, not legal advice.

## Quotes that may be cited (checked against the books)
1. "The fundamental problem of requirements definition is ambiguity." — ER1 › Ch 9 Reducing Ambiguity from Start to Finish
2. "Beware of comparative words, like 'small' or 'inexpensive,' in problem statements." — ER1 › Ch 2 › 2.1.2
3. "An attribute does not stand alone, but is rather a modifier of one or more functions." — ER2 › Ch 15 › 15.3
4. "A constraint is a mandatory condition placed on an M attribute… a constraint must be defined so as to enable participants to determine objectively whether or not it has been satisfied in the finished product." — ER2 › Ch 16 › 16.1
5. "Nothing about an attribute itself tells us whether it is a constraint or a preference." — ER2 › Ch 17 › 17.3
6. "What part of the problem statement led you to those inferences?" — ER2 › Ch 19 › 19.2.2
7. "No single failure of requirements work leads to more lawsuits than the confident declaration, 'No sane person would do that!'" — ER2 › Ch 22 › 22.1.3
8. "Every requirement should be traceable to its source." — ER2 › Ch 24 › 24.1.3
9. "Frame every technical question so the reply will be self-validating." — RSAD › Part IV › Self-Validating Questions
10. "If you can't think of at least three things that might be wrong with your understanding of the problem, you don't understand the problem." — ARYLO › Part 1 › Ch 7
11. "Testing is, at best, sampling." — PS › Ch 3
12. "The key to NFRs is usually tests. In the first instance, a NFR is a request for testing." — LBR › 9 Working with Nonfunctional Requirements
13. "This approach demands quantifying NFRs: How fast is fast? How secure is secure?" — LBR › 9 › Specifying the Requirements
14. "Examples illustrate the rules, but they do not replace them." — DISC › Ch 3 › 3.5
15. "There are no situations where the "or" conjunction is acceptable." — FORM › Ch 3 › 3.11
16. "Write every sentence as though it will succeed." — UNIFY › 12. Use cases contain multiple scenarios
17. "Even if you're not going to actively measure an important aspect of quality, try to quantify it." — FIFTY › Quantify even if you cannot measure
18. "The delinquent path – consider the security risks that need testing, like authentication, authorisation, permissions, data confidentiality and so on." — FIFTY › Tap into your emotions
19. "When configuring a new monitor, ideally you will test that it works by causing an issue that the monitor should detect." — Clokie › Testing monitoring and alerting
20. "automated tests that run on unrealistically small data sets (i.e., '100's of MB vs. 100's of GBs'), which led to production failures." — DOH › Ch 12 › CSG case study
21. "It's not a functional requirement – testability and other operational features never make it into the backlog. But these features are what turns functionality into a product." — TGST › Introduction

Note: ER2 §24.5 step 2 contains a likely typo ("a choice, an imposition, or an agreement" for "assumption") — don't quote it.
