# Integration tests

- Location: `tests/integration`.
- Use Testcontainers for a real Postgres. Do not mock the database:
  mocked tests have passed while production broke.
- Tag slow tests with `@slow`.
