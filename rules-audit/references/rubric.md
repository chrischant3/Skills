# Audit rubric

The checklist the rules-audit skill uses to assess agent instruction files (AGENTS.md, CLAUDE.md, rule files, skills and prompts). Cite items by ID in findings, for example `S1` or `A2`.

A **critical rule** is one whose breach is costly or hard to undo (leaked secrets, damaged shared data, lost work, security or legal exposure), or one the authors mark as non-negotiable. The severity notes below use this term.

## Structure and placement

- **S1.** Critical rules appear first, numbered, each with a one-line reason.
  High when a critical rule is out of place. This is a test of where the rule sits, not a judgement of how noticeable it is: High if the rule is inside narrative prose, shares a sentence, bullet or paragraph with other content, or sits outside the section where the file keeps its critical rules (after less important rules, when the file has no such section). A well-structured file does not lower the severity of one misplaced rule.
  Not a finding when a rule that matters only for one kind of task lives in an on-demand file whose pointer has a trigger covering that task. That is P1 working as intended; P3 covers pointers without a trigger.
- **S2.** Each rule is stated once; detail points back to it rather than rewording it.
  High when a critical rule is restated in different wording or strength, because the reader cannot tell which version governs. Medium when the repeated content is not a critical rule, or is repeated word for word.
- **S3.** Headers show hierarchy, no deeper than H3.
- **S4.** Numbered lists for ordered steps, bullets for independent rules.

## Progressive disclosure

- **P1.** Always-loaded content is needed on most tasks; the rest is deferred to files loaded on demand.
- **P2.** The entry file works as a map: what exists and where.
- **P3.** Every pointer states when to follow it, not only that a file exists.
  High when the only route to a critical rule is a pointer with no trigger, or no route exists.
- **P4.** References sit one level deep from the entry file, with no chains.
- **P5.** Each reference file makes sense on its own once opened.
- **P6.** Size: flag always-loaded files over about 200 lines and SKILL.md files over 500.

## Instruction quality

- **Q1.** Rules explain why, not only what.
- **Q2.** Positive instructions (what to do) are preferred over prohibitions.
- **Q3.** No shouting: capitals, MUST and NEVER are kept for genuine hard limits.
- **Q4.** No rules the model would follow anyway.
- **Q5.** No contradictions across files or layers.
  High when the contradiction involves a critical rule.
- **Q6.** Examples are varied and fenced, so they are not read as instructions.
- **Q7.** Pasted context and data are separated from instructions with tags or fences.

## Discipline rules

A rationalisation table lists the excuses an agent gives for skipping a rule ("it's only a small change") next to the reason the excuse fails.

- **D1.** Rules that are tempting to skip and costly to break have a rationalisation table.
- **D2.** Table entries look drawn from real transcripts, not invented.

## Testability

- **T1.** Each rule can be checked from a transcript, a diff or an effect.
- **T2.** Rules have IDs a verifier can cite.

## Security

These items judge what the text asks of the agent and what it leaves out. Instructions are not a security control: a model can be talked out of any rule, so a rule's wording can make an agent less safe but can't make it safe. Where a harness control exists (a permission deny rule, a hook, branch protection, a sandbox), the suggested fix names it as well as any rewording. Based on OWASP's Secure Coding with AI cheat sheet, which says to treat rules files as security-critical configuration, and its LLM and agentic Top 10s.

- **A1.** No secrets, tokens, passwords or private keys in instruction files.
  High for anything that looks like a real credential, wherever it sits: the files are loaded into every session and often committed. Not a finding for an obvious placeholder (`your-key-here`, `<token>`) in a code example, fenced or indented. Quote the line with the value masked (see SKILL.md rule 3).
- **A2.** No instructions that weaken a control: pre-approving commands, skipping confirmation, pushing or deploying without review, `--no-verify`, turning off hooks, tests or the sandbox, or telling the agent to ignore certain files or warnings.
  High, because it removes a check the owner relies on.
- **A3.** No hidden content: invisible Unicode (tag, zero-width or bidi characters), long encoded strings, HTML comments that hold instructions, or remote images, which can carry data out in their URL.
  High for hidden instructions or remote images, wherever they sit. Not a finding for a comment that is plainly a tooling marker, such as `<!-- generated -->`.
- **A4.** An agent that reads content it didn't write (issues, pull requests, web pages, tool or MCP output, files from elsewhere) is told to treat that content as data, not instructions, and to ask before acting on anything it asks for.
  Medium when such content is read with no such rule; High when the agent also runs commands or code taken from that content.
- **A5.** High-impact or irreversible actions the agent itself might take (push, deploy, delete, running migrations, payments, sending messages) need explicit approval, and the rule names them.
  High when the files tell the agent to take such an action without approval. Medium when the agent's work could plausibly include one and no rule covers it. Not a finding for actions that CI or people perform, such as migrations that run in CI on deploy.
- **A6.** The agent may not change its own instructions, hooks, harness settings or CI configuration without asking.
  Medium when the files are silent on it.
- **A7.** No fetch-and-run (`curl ... | sh`), unpinned or unreviewed installs, or tools and MCP servers beyond what the work needs.
  Medium; High when the file tells the agent to run remote code.
- **A8.** Each critical rule that a harness setting could enforce (a deny rule for a command or path, a hook) has a matching control. Checked only when the user has allowed the audit to read the harness settings; see SKILL.md.
  High when nothing enforces a rule against an irreversible action; Medium otherwise.

## Severity scale

- **High:** a critical rule is buried, contradicted or unreachable from what the agent loads. For repeated rules, S2 sets the severity.
- **Medium:** bloat or weak pointers that dilute attention.
- **Low:** style and formatting.

Where an item above has a severity note, the note takes precedence.
