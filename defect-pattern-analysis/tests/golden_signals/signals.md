# Ticket signals

Three separate groups of signals: clarity, complexity and flow. They are never combined into one score. Every figure is for a group of defects (all defects, a team, a period or a defect type), never a person. Groups with fewer than 5 defects are suppressed, and a suppressed group is never named. Figures are medians, or the number and share of defects showing a signal. At most they show correlations, not causes.

## Summary

- defects_analysed: 71
- changelog_incomplete_defects: 7
- comments_incomplete_defects: suppressed
- defects_done: 52
- defects_with_unmapped_statuses: 0
- source_control: available
- defects_linked_to_source_control: 57

## Clarity

How clearly the defect was described and understood. The rubric score counts how many of four parts the description has: steps to reproduce, expected against actual, environment and acceptance criteria.

- rubric_score: median rubric score, 0 to 4
- has_repro_steps: description gives steps to reproduce
- has_expected_vs_actual: description gives expected and actual results
- has_environment: description names the environment
- has_acceptance_criteria: acceptance criteria given
- edited_after_start: description or acceptance criteria edited after work started
- clarifying_question: at least one clarifying-question comment
- reopened: reopened at least once

| grouping | group | signal | defects | with signal | share | median |
|---|---|---|---|---|---|---|
| all | all defects | rubric_score | 71 |  |  | 2.0 |
| all | all defects | has_repro_steps | 71 | 50 | 0.7 |  |
| all | all defects | has_expected_vs_actual | 71 | 33 | 0.46 |  |
| all | all defects | has_environment | 71 | 37 | 0.52 |  |
| all | all defects | has_acceptance_criteria | 71 | 36 | 0.51 |  |
| all | all defects | edited_after_start | 51 | 19 | 0.37 |  |
| all | all defects | clarifying_question | suppressed | suppressed | suppressed |  |
| all | all defects | reopened | suppressed | suppressed | suppressed |  |
| team | Accounts | rubric_score | 20 |  |  | 2.0 |
| team | Accounts | has_repro_steps | 20 | 14 | 0.7 |  |
| team | Accounts | has_expected_vs_actual | 20 | 10 | 0.5 |  |
| team | Accounts | has_environment | 20 | 10 | 0.5 |  |
| team | Accounts | has_acceptance_criteria | 20 | 10 | 0.5 |  |
| team | Accounts | edited_after_start | 14 | 5 | 0.36 |  |
| team | Accounts | clarifying_question | suppressed | suppressed | suppressed |  |
| team | Accounts | reopened | suppressed | suppressed | suppressed |  |
| team | Payments | rubric_score | 30 |  |  | 2.0 |
| team | Payments | has_repro_steps | 30 | 19 | 0.63 |  |
| team | Payments | has_expected_vs_actual | 30 | 9 | 0.3 |  |
| team | Payments | has_environment | 30 | 12 | 0.4 |  |
| team | Payments | has_acceptance_criteria | 30 | 15 | 0.5 |  |
| team | Payments | edited_after_start | 23 | 9 | 0.39 |  |
| team | Payments | clarifying_question | suppressed | suppressed | suppressed |  |
| team | Payments | reopened | suppressed | suppressed | suppressed |  |
| team | Search | rubric_score | 6 |  |  | 2.0 |
| team | Search | has_repro_steps | suppressed | suppressed | suppressed |  |
| team | Search | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| team | Search | has_environment | suppressed | suppressed | suppressed |  |
| team | Search | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| team | Search | edited_after_start | suppressed | suppressed | suppressed |  |
| team | Search | clarifying_question | suppressed | suppressed | suppressed |  |
| team | Search | reopened | suppressed | suppressed | suppressed |  |
| team | Web | rubric_score | 5 |  |  | 3.0 |
| team | Web | has_repro_steps | 5 | 5 | 1.0 |  |
| team | Web | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| team | Web | has_environment | suppressed | suppressed | suppressed |  |
| team | Web | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| team | Web | edited_after_start | suppressed | suppressed | suppressed |  |
| team | Web | clarifying_question | suppressed | suppressed | suppressed |  |
| team | Web | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-01 | rubric_score | 11 |  |  | 3.0 |
| period | 2026-01 | has_repro_steps | 11 | 11 | 1.0 |  |
| period | 2026-01 | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| period | 2026-01 | has_environment | suppressed | suppressed | suppressed |  |
| period | 2026-01 | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| period | 2026-01 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-01 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-01 | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-02 | rubric_score | 12 |  |  | 2.5 |
| period | 2026-02 | has_repro_steps | suppressed | suppressed | suppressed |  |
| period | 2026-02 | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| period | 2026-02 | has_environment | suppressed | suppressed | suppressed |  |
| period | 2026-02 | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| period | 2026-02 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-02 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-02 | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-03 | rubric_score | 12 |  |  | 1.5 |
| period | 2026-03 | has_repro_steps | 12 | 7 | 0.58 |  |
| period | 2026-03 | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| period | 2026-03 | has_environment | suppressed | suppressed | suppressed |  |
| period | 2026-03 | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| period | 2026-03 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-03 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-03 | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-04 | rubric_score | 12 |  |  | 2.0 |
| period | 2026-04 | has_repro_steps | suppressed | suppressed | suppressed |  |
| period | 2026-04 | has_expected_vs_actual | 12 | 5 | 0.42 |  |
| period | 2026-04 | has_environment | 12 | 6 | 0.5 |  |
| period | 2026-04 | has_acceptance_criteria | 12 | 7 | 0.58 |  |
| period | 2026-04 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-04 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-04 | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-05 | rubric_score | 12 |  |  | 2.0 |
| period | 2026-05 | has_repro_steps | 12 | 5 | 0.42 |  |
| period | 2026-05 | has_expected_vs_actual | suppressed | suppressed | suppressed |  |
| period | 2026-05 | has_environment | 12 | 6 | 0.5 |  |
| period | 2026-05 | has_acceptance_criteria | 12 | 6 | 0.5 |  |
| period | 2026-05 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-05 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-05 | reopened | suppressed | suppressed | suppressed |  |
| period | 2026-06 | rubric_score | 12 |  |  | 2.0 |
| period | 2026-06 | has_repro_steps | suppressed | suppressed | suppressed |  |
| period | 2026-06 | has_expected_vs_actual | 12 | 5 | 0.42 |  |
| period | 2026-06 | has_environment | suppressed | suppressed | suppressed |  |
| period | 2026-06 | has_acceptance_criteria | suppressed | suppressed | suppressed |  |
| period | 2026-06 | edited_after_start | suppressed | suppressed | suppressed |  |
| period | 2026-06 | clarifying_question | suppressed | suppressed | suppressed |  |
| period | 2026-06 | reopened | suppressed | suppressed | suppressed |  |

4 groups suppressed: each had fewer than 5 defects, or was hidden so that a small group can't be worked out from the totals.

## Complexity

How much the defect touched. Source control figures count only defects linked in step 5; a defect with no link is left out, not counted as zero. Lines changed aren't available, because diff text is dropped during anonymisation.

- linked_issues: median linked issues
- comments: median comments
- changes: median merge or pull requests
- commits: median commits
- files_changed: median files changed
- repos_touched: median repos touched

| grouping | group | signal | defects | with signal | share | median |
|---|---|---|---|---|---|---|
| all | all defects | linked_issues | 71 |  |  | 2.0 |
| all | all defects | comments | suppressed |  |  | suppressed |
| all | all defects | changes | 57 |  |  | 2.0 |
| all | all defects | commits | 57 |  |  | 3.0 |
| all | all defects | files_changed | 57 |  |  | 7.0 |
| all | all defects | repos_touched | 57 |  |  | 1.0 |
| team | Accounts | linked_issues | 20 |  |  | 2.0 |
| team | Accounts | comments | suppressed |  |  | suppressed |
| team | Accounts | changes | suppressed |  |  | suppressed |
| team | Accounts | commits | suppressed |  |  | suppressed |
| team | Accounts | files_changed | suppressed |  |  | suppressed |
| team | Accounts | repos_touched | suppressed |  |  | suppressed |
| team | Payments | linked_issues | 30 |  |  | 2.0 |
| team | Payments | comments | suppressed |  |  | suppressed |
| team | Payments | changes | 22 |  |  | 2.0 |
| team | Payments | commits | 22 |  |  | 3.5 |
| team | Payments | files_changed | 22 |  |  | 6.5 |
| team | Payments | repos_touched | 22 |  |  | 1.0 |
| team | Search | linked_issues | 6 |  |  | 1.5 |
| team | Search | comments | 6 |  |  | 3.0 |
| team | Search | changes | 6 |  |  | 2.5 |
| team | Search | commits | 6 |  |  | 3.5 |
| team | Search | files_changed | 6 |  |  | 4.5 |
| team | Search | repos_touched | 6 |  |  | 1.5 |
| team | Web | linked_issues | 5 |  |  | 2.0 |
| team | Web | comments | suppressed |  |  | suppressed |
| team | Web | changes | suppressed |  |  | suppressed |
| team | Web | commits | suppressed |  |  | suppressed |
| team | Web | files_changed | suppressed |  |  | suppressed |
| team | Web | repos_touched | suppressed |  |  | suppressed |
| period | 2026-01 | linked_issues | 11 |  |  | 3.0 |
| period | 2026-01 | comments | 11 |  |  | 3.0 |
| period | 2026-01 | changes | suppressed |  |  | suppressed |
| period | 2026-01 | commits | suppressed |  |  | suppressed |
| period | 2026-01 | files_changed | suppressed |  |  | suppressed |
| period | 2026-01 | repos_touched | suppressed |  |  | suppressed |
| period | 2026-02 | linked_issues | 12 |  |  | 1.5 |
| period | 2026-02 | comments | suppressed |  |  | suppressed |
| period | 2026-02 | changes | suppressed |  |  | suppressed |
| period | 2026-02 | commits | suppressed |  |  | suppressed |
| period | 2026-02 | files_changed | suppressed |  |  | suppressed |
| period | 2026-02 | repos_touched | suppressed |  |  | suppressed |
| period | 2026-03 | linked_issues | 12 |  |  | 1.0 |
| period | 2026-03 | comments | suppressed |  |  | suppressed |
| period | 2026-03 | changes | 12 |  |  | 2.0 |
| period | 2026-03 | commits | 12 |  |  | 3.0 |
| period | 2026-03 | files_changed | 12 |  |  | 5.0 |
| period | 2026-03 | repos_touched | 12 |  |  | 1.0 |
| period | 2026-04 | linked_issues | 12 |  |  | 1.0 |
| period | 2026-04 | comments | suppressed |  |  | suppressed |
| period | 2026-04 | changes | suppressed |  |  | suppressed |
| period | 2026-04 | commits | suppressed |  |  | suppressed |
| period | 2026-04 | files_changed | suppressed |  |  | suppressed |
| period | 2026-04 | repos_touched | suppressed |  |  | suppressed |
| period | 2026-05 | linked_issues | 12 |  |  | 2.0 |
| period | 2026-05 | comments | suppressed |  |  | suppressed |
| period | 2026-05 | changes | suppressed |  |  | suppressed |
| period | 2026-05 | commits | suppressed |  |  | suppressed |
| period | 2026-05 | files_changed | suppressed |  |  | suppressed |
| period | 2026-05 | repos_touched | suppressed |  |  | suppressed |
| period | 2026-06 | linked_issues | 12 |  |  | 2.0 |
| period | 2026-06 | comments | suppressed |  |  | suppressed |
| period | 2026-06 | changes | 7 |  |  | 2.0 |
| period | 2026-06 | commits | 7 |  |  | 2.0 |
| period | 2026-06 | files_changed | 7 |  |  | 9.0 |
| period | 2026-06 | repos_touched | 7 |  |  | 1.0 |

4 groups suppressed: each had fewer than 5 defects, or was hidden so that a small group can't be worked out from the totals.

## Flow

Flow describes the system the work moves through (queues, hand-offs and waiting), not the ticket and not the people working on it. Times are in hours and cover defects that reached a done status. Time spent done before a reopen, or in a status missing from the config, is neither active nor waiting.

- lead_time_hours: median hours from created to done
- cycle_time_hours: median hours from work started to done
- active_hours: median hours active once started
- waiting_hours: median hours waiting once started
- flow_efficiency: median share of active time in active plus waiting time
- status_changes: median status changes
- backward_move: moved backward on the board at least once

| grouping | group | signal | defects | with signal | share | median |
|---|---|---|---|---|---|---|
| all | all defects | lead_time_hours | 52 |  |  | 91.0 |
| all | all defects | cycle_time_hours | 45 |  |  | 78.0 |
| all | all defects | active_hours | 45 |  |  | 53.0 |
| all | all defects | waiting_hours | 45 |  |  | 31.0 |
| all | all defects | flow_efficiency | 45 |  |  | 0.67 |
| all | all defects | status_changes | 64 |  |  | 4.0 |
| all | all defects | backward_move | 64 | 14 | 0.22 |  |
| team | Accounts | lead_time_hours | 15 |  |  | 105.0 |
| team | Accounts | cycle_time_hours | 13 |  |  | 104.0 |
| team | Accounts | active_hours | 13 |  |  | 62.0 |
| team | Accounts | waiting_hours | 13 |  |  | 39.0 |
| team | Accounts | flow_efficiency | 13 |  |  | 0.64 |
| team | Accounts | status_changes | suppressed |  |  | suppressed |
| team | Accounts | backward_move | suppressed | suppressed | suppressed |  |
| team | Payments | lead_time_hours | 22 |  |  | 85.5 |
| team | Payments | cycle_time_hours | 19 |  |  | 76.0 |
| team | Payments | active_hours | 19 |  |  | 48.0 |
| team | Payments | waiting_hours | 19 |  |  | 25.0 |
| team | Payments | flow_efficiency | 19 |  |  | 0.7 |
| team | Payments | status_changes | suppressed |  |  | suppressed |
| team | Payments | backward_move | suppressed | suppressed | suppressed |  |
| team | Search | lead_time_hours | 6 |  |  | 83.0 |
| team | Search | cycle_time_hours | suppressed |  |  | suppressed |
| team | Search | active_hours | suppressed |  |  | suppressed |
| team | Search | waiting_hours | suppressed |  |  | suppressed |
| team | Search | flow_efficiency | suppressed |  |  | suppressed |
| team | Search | status_changes | 6 |  |  | 4.0 |
| team | Search | backward_move | suppressed | suppressed | suppressed |  |
| team | Web | lead_time_hours | suppressed |  |  | suppressed |
| team | Web | cycle_time_hours | suppressed |  |  | suppressed |
| team | Web | active_hours | suppressed |  |  | suppressed |
| team | Web | waiting_hours | suppressed |  |  | suppressed |
| team | Web | flow_efficiency | suppressed |  |  | suppressed |
| team | Web | status_changes | suppressed |  |  | suppressed |
| team | Web | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-01 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-01 | cycle_time_hours | suppressed |  |  | suppressed |
| period | 2026-01 | active_hours | suppressed |  |  | suppressed |
| period | 2026-01 | waiting_hours | suppressed |  |  | suppressed |
| period | 2026-01 | flow_efficiency | suppressed |  |  | suppressed |
| period | 2026-01 | status_changes | suppressed |  |  | suppressed |
| period | 2026-01 | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-02 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-02 | cycle_time_hours | 5 |  |  | 59.0 |
| period | 2026-02 | active_hours | 5 |  |  | 43.0 |
| period | 2026-02 | waiting_hours | 5 |  |  | 17.0 |
| period | 2026-02 | flow_efficiency | 5 |  |  | 0.77 |
| period | 2026-02 | status_changes | suppressed |  |  | suppressed |
| period | 2026-02 | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-03 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-03 | cycle_time_hours | suppressed |  |  | suppressed |
| period | 2026-03 | active_hours | suppressed |  |  | suppressed |
| period | 2026-03 | waiting_hours | suppressed |  |  | suppressed |
| period | 2026-03 | flow_efficiency | suppressed |  |  | suppressed |
| period | 2026-03 | status_changes | suppressed |  |  | suppressed |
| period | 2026-03 | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-04 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-04 | cycle_time_hours | 6 |  |  | 94.5 |
| period | 2026-04 | active_hours | 6 |  |  | 55.5 |
| period | 2026-04 | waiting_hours | 6 |  |  | 39.5 |
| period | 2026-04 | flow_efficiency | 6 |  |  | 0.64 |
| period | 2026-04 | status_changes | suppressed |  |  | suppressed |
| period | 2026-04 | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-05 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-05 | cycle_time_hours | suppressed |  |  | suppressed |
| period | 2026-05 | active_hours | suppressed |  |  | suppressed |
| period | 2026-05 | waiting_hours | suppressed |  |  | suppressed |
| period | 2026-05 | flow_efficiency | suppressed |  |  | suppressed |
| period | 2026-05 | status_changes | suppressed |  |  | suppressed |
| period | 2026-05 | backward_move | suppressed | suppressed | suppressed |  |
| period | 2026-06 | lead_time_hours | suppressed |  |  | suppressed |
| period | 2026-06 | cycle_time_hours | 7 |  |  | 105.0 |
| period | 2026-06 | active_hours | 7 |  |  | 68.0 |
| period | 2026-06 | waiting_hours | 7 |  |  | 44.0 |
| period | 2026-06 | flow_efficiency | 7 |  |  | 0.66 |
| period | 2026-06 | status_changes | suppressed |  |  | suppressed |
| period | 2026-06 | backward_move | suppressed | suppressed | suppressed |  |

### Time in each status

Median hours spent in each status by done defects that entered it, before they were done.

| grouping | group | status | defects | median hours |
|---|---|---|---|---|
| all | all defects | To Do | 52 | 17.5 |
| all | all defects | In Progress | 45 | 33.0 |
| all | all defects | In Review | 45 | 31.0 |
| all | all defects | In Test | 45 | 28.0 |
| all | all defects | Done | suppressed | suppressed |
| team | Accounts | To Do | 15 | 28.0 |
| team | Accounts | In Progress | 13 | 33.0 |
| team | Accounts | In Review | 13 | 39.0 |
| team | Accounts | In Test | 13 | 25.0 |
| team | Payments | To Do | 22 | 17.0 |
| team | Payments | In Progress | 19 | 27.0 |
| team | Payments | In Review | 19 | 25.0 |
| team | Payments | In Test | 19 | 32.0 |
| team | Payments | Done | suppressed | suppressed |
| team | Search | To Do | 6 | 12.5 |
| team | Search | In Progress | suppressed | suppressed |
| team | Search | In Review | suppressed | suppressed |
| team | Search | In Test | suppressed | suppressed |
| team | Search | Done | suppressed | suppressed |
| team | Web | To Do | suppressed | suppressed |
| team | Web | In Progress | suppressed | suppressed |
| team | Web | In Review | suppressed | suppressed |
| team | Web | In Test | suppressed | suppressed |
| period | 2026-01 | To Do | suppressed | suppressed |
| period | 2026-01 | In Progress | suppressed | suppressed |
| period | 2026-01 | In Review | suppressed | suppressed |
| period | 2026-01 | In Test | suppressed | suppressed |
| period | 2026-01 | Done | suppressed | suppressed |
| period | 2026-02 | To Do | suppressed | suppressed |
| period | 2026-02 | In Progress | 5 | 15.0 |
| period | 2026-02 | In Review | 5 | 17.0 |
| period | 2026-02 | In Test | 5 | 33.0 |
| period | 2026-03 | To Do | suppressed | suppressed |
| period | 2026-03 | In Progress | suppressed | suppressed |
| period | 2026-03 | In Review | suppressed | suppressed |
| period | 2026-03 | In Test | suppressed | suppressed |
| period | 2026-03 | Done | suppressed | suppressed |
| period | 2026-04 | To Do | suppressed | suppressed |
| period | 2026-04 | In Progress | 6 | 23.5 |
| period | 2026-04 | In Review | 6 | 39.5 |
| period | 2026-04 | In Test | 6 | 29.5 |
| period | 2026-04 | Done | suppressed | suppressed |
| period | 2026-05 | To Do | suppressed | suppressed |
| period | 2026-05 | In Progress | suppressed | suppressed |
| period | 2026-05 | In Review | suppressed | suppressed |
| period | 2026-05 | In Test | suppressed | suppressed |
| period | 2026-06 | To Do | suppressed | suppressed |
| period | 2026-06 | In Progress | 7 | 45.0 |
| period | 2026-06 | In Review | 7 | 44.0 |
| period | 2026-06 | In Test | 7 | 32.0 |

4 groups suppressed: each had fewer than 5 defects, or was hidden so that a small group can't be worked out from the totals.

## Clarity and rework within complexity bands

Bands are terciles of files changed among defects linked to source control: low (up to 5 files), middle (6 to 8 files), high (more than 8 files). Rework means the defect was reopened or moved backward on the board. Clarity is higher with a rubric score of 3 or more out of 4. Compare clarity within a band, not across bands. These are correlations, not causes.

| band | files changed | clarity | defects | with rework | share |
|---|---|---|---|---|---|
| low | up to 5 files | lower | suppressed | suppressed | suppressed |
| low | up to 5 files | higher | suppressed | suppressed | suppressed |
| middle | 6 to 8 files | lower | suppressed | suppressed | suppressed |
| middle | 6 to 8 files | higher | suppressed | suppressed | suppressed |
| high | more than 8 files | lower | suppressed | suppressed | suppressed |
| high | more than 8 files | higher | suppressed | suppressed | suppressed |

## Caveats

- Signals are read from ticket history and text, so they show how the work was recorded as well as how it went.
- Defects with an incomplete changelog or incomplete comments are left out of the signals that need them, never counted as zero.
- Time in a status missing from signals.yaml is neither active nor waiting; add missing statuses and run again if defects_with_unmapped_statuses is high.
- Clarifying questions are found by wording, in anonymised comments, and will miss some and catch others.
