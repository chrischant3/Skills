# AGENTS.md: orders service

TypeScript, Node 20, Postgres. Source in `src`, tests in `tests`.

## Non-negotiable rules

1. **Never commit secrets.** API keys, passwords and tokens go in
   environment variables. `.env` is git-ignored. Leaked secrets cannot be
   un-leaked.
2. **Never edit an existing migration.** Create a new one instead.
   Editing a merged migration breaks every other database.
3. **Never edit `src/generated` by hand.** Run `npm run generate`.
   Manual edits are overwritten.
4. **Test first.** Write a failing test, see it fail, then implement.
5. **Ask before adding a dependency.** Propose it and wait for approval.
6. **Finish with `npm test` and `npm run lint` passing.**

## Working conventions

- Keep changes small and focused; one concern per change.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `test:`).
- Log with `src/lib/logger`, never `console.log`. Never log personal data
  such as names or email addresses.
- Unit tests live beside the code in `__tests__`.

## Read these when relevant

- Creating or changing database schema: read `docs/agents/migrations.md`.
- Writing or changing integration tests: read
  `docs/agents/integration-tests.md`.
- Creating or changing anything in `src/ui`: read
  `docs/agents/ui-accessibility.md`.
