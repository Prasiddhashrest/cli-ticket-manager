# Changelog

## v1.2 — Technician assignment and workload dashboard

- Added nullable `assigned_to` field to `Ticket` model and SQLite storage.
- Added automatic schema migration so pre-existing tickets are preserved.
- Added `assign` and `unassign` CLI commands and technician filters for `list`.
- Added optional `--agent` argument when creating tickets via CLI.
- Added assignment form, technician filter, unassigned metric, and workload chart to the Streamlit dashboard.
- Added assignment and migration regression tests.

## v1.1 — Streamlit dashboard

- Added interactive ticket creation, filtering, status updates, and CSV export.
- Added counts and category/priority charts.

## v1.0 — Python CLI

- Added SQLite-backed ticket create, list, inspect, resolve, and reopen commands.
- Added initial unit tests and GitHub Actions CI.
