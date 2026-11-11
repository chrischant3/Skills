# Reading eval scores

There is no standard score for a good skill. A score depends on how hard the cases are as much as on the skill: a suite of easy cases gives 1.0 to almost anything, and a demanding suite can hold a good skill at 0.85. So read the score alongside the four signs below.

These are rules of thumb from practice, not a published benchmark.

## Score with the skill

- **0.9 to 1.0 on the main model**, with every case at or above the pass mark, is what a skill ready to publish usually looks like.
- **Safety cases score 1.0 on every run.** Anything less is a failure, whatever the average.
- **Below about 0.8 on the main model** usually means the skill isn't ready.

## Gain over no skill

This matters more than the score. Compare each case with the same prompt run without the skill.

- Cases that measure the skill should score low without it, roughly 0 to 0.5, and high with it.
- An average gain of about +0.3 or more is a good sign.
- A gain near zero means the skill adds little, or the cases are too easy to show what it adds.
- A negative gain means the skill makes that case worse. Investigate before publishing.

Cases that score the same with and without the skill are still useful as regression guards, as long as you know that's what they are. A suite made only of guards can't show the skill is worth installing.

## Spread across models

Smaller models usually score a little lower. Losing one case on the smallest model is normal. A big drop means the skill relies on the model working out what it means; make the instructions more explicit, or check whether the smaller model is loading the skill at all.

Record each model's scores separately. Never average them, because a skill that fails on one model fails for everyone using that model.

## Run-to-run consistency

Model output varies, so each case runs several times. A strong skill passes every run, not two out of three. A case that flips between runs is either testing something the skill doesn't control, or the skill's instruction for it is too weak.

## A worked example

This skill's own suite of nine cases, three runs each:

| | Opus | Sonnet | Haiku |
|---|---|---|---|
| Score with the skill | 1.00 | 0.98 | 0.96 |
| Cases passed | 9 of 9 | 9 of 9 | 8 of 9 |
| Average gain over no skill | +0.43 | +0.44 | +0.51 |

Read against the signs above: high scores on every model, a clear gain over no skill, and four cases that go from 0 without the skill to 1.0 with it. Haiku drops one case, which is the expected spread. Three cases score the same with and without the skill on every model, and are kept as regression guards.

## A caution

Cases written by the person who wrote the skill, at the same time, tend to flatter it. Treat a first set of high scores as a starting point. The real test is cases taken from failures people actually hit once the skill is in use.
