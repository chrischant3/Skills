# Assessing the default criteria

How to judge each criterion in the [default definition](default-definition-of-ready.md). Judge what's written, not what the item might have meant.

## Independent

- **Met:** no dependencies, or each one is named and either already done or agreed with whoever owns it.
- **Not met:** the item needs other unfinished work and doesn't say so, or names it with no agreement ("needs the new API").

Items linked by dependencies are hard to estimate. Sometimes the fix is a larger item, or a different split.

## Negotiable

- **Met:** it states the need and leaves the team room to choose how.
- **Partly met:** it dictates the solution in detail (exact components, tables, libraries) without saying why that one.

## Valuable

- **Met:** it says who benefits and how ("so that I can return books on time").
- **Not met:** no beneficiary or no reason, only a task ("Add an export button").

## Estimable

Don't give an estimate. Say whether the team could size it from what's written. If not, name the reason:

| Reason | Cynefin domain | What helps |
|---|---|---|
| Missing domain knowledge | Complex | A team conversation to bring everyone up to speed |
| Missing technical knowledge | Complicated | A time-boxed spike to find out |
| The item is too big | Complex | Splitting it (see Small) |

## Small

- **Met:** it fits in one iteration.
- **Not met:** it bundles several features. Suggest a split and name the smaller items.

Two kinds of large item:

- **Compound:** several items in one. "A member can manage their account" is register, log in, reset a password, change address, and so on. Split into items that each deliver something; join tiny ones back together ("add and edit an address").
- **Complex:** too uncertain to plan. Split into a time-boxed spike to find out (regulations, technical details, third-party capabilities) and a development item that uses what the spike found.

## Testable

- **Met:** someone could tell, without asking the author, whether each acceptance criterion holds.
- **Not met:** criteria rely on words with no threshold or test: "fast", "relevant", "user-friendly", "works well", "as expected", "the export works". Say what would make each measurable, such as a time limit, the results expected for a given search, or the devices it must work on. Suggest the kind of measure; don't pick the number for the team.

## Description

- **Met:** it says what the item is, what it delivers and why.
- **Partly met:** it gives the what but not the why, or the reverse.

## Acceptance criteria

- **Met:** present, specific and measurable, and together they say what must be true for the item to be accepted.
- **Not met:** missing, "TBC", or only examples. Examples illustrate the rules; acceptance criteria state them.

A missing or untestable set of acceptance criteria is the first thing to fix, because without it nobody can tell when the item is done.

## Examples

- **Met:** each example has a context, an action and an expected result. Any format will do, such as Given/When/Then or a scenario named "The one where…".
- **Partly met:** examples exist, but some lack an expected result or use vague ones ("I see good results").
- **Not met:** none.

## Open questions

- **Met:** listed, or the item says there are none, and none blocks starting the work. A question the item explicitly puts out of scope or defers doesn't block.
- **Not met:** a listed question must be answered before the work can start.

Open questions that are listed and don't block lead to the verdict **Ready with questions**, not Not ready.

## Verification

- **Met:** it lists the evidence that will show the acceptance criteria are met: test results, screenshots, output files, a reviewer's sign-off on something specific.
- **Partly met:** vague evidence ("tests pass", "the PO is happy with it").
- **Not met:** none.

Acceptance criteria say what must be true; verification says what will exist to prove it.
