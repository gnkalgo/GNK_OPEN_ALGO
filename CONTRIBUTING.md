# Contributing to GNK ALGO

Use original GNK implementation decisions. Consult reference projects for general concepts; do not import source, assets, schemas or integrations without recording authorization, exact provenance and license obligations in docs/THIRD-PARTY-POLICY.md. Keep third-party notices intact. The repository owner's distribution license decision remains pending.

Preserve existing user changes and branding. Keep changes focused; do not stage generated reports, browser captures, secrets, test output or adjacent repositories. Add dependencies only with an updated lockfile and regenerated dependency inventory. Tests must cover financial effects, account isolation, risk failure and uncertain outcomes when those behaviors change.

Run frontend build/unit tests, backend Ruff/Pytest and migration checks. PostgreSQL concurrency tests are required before production acceptance; SQLite and fake Redis validate local behavior only. Update docs/TEST-RESULTS.md with what actually ran. Never turn on live execution to make a demo appear complete.
