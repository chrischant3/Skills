# Database migrations

Applies rule 2 in AGENTS.md.

- Migrations live in `db/migrations` and run in CI on deploy.
- Create one with `npm run migrate:create <name>`.
- Every migration needs a working down step.
