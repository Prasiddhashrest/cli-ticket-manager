# Changelog

## v1.3 — Ticket editing, activity history, and UI refresh

- Add `edit` and `history` CLI commands and global `activity` command.
- Edit ticket title, description, priority, and category in the CLI or Streamlit dashboard.
- Record new ticket creations, field edits, technician changes, and status changes in an append-only `ticket_events` SQLite table.
- Add `updated_at` and a safe, repeatable migration from older local databases.
- Avoid duplicate history entries when an update doesn't change anything.
- Organize the dashboard into **Overview**, **Manage tickets**, **New ticket**, and **Activity log** tabs, with a ticket trend chart and clean metric cards.
- Add regression tests for updates, event history, migration, and CLI commands.

**Important:** Actions performed before upgrading to v1.3 have no event records. Historical actions cannot be reconstructed; tickets themselves are preserved.

## v1.2 — Technician assignment

- Added technician assignment, unassignment, filtering, and workload analytics.
- Added the `assigned_to` SQLite migration and assignment tests.

## v1.1 — Streamlit dashboard

- Added browser-based ticket management, search, charts and CSV export.

## v1.0 — CLI

- Added Python ticket management with SQLite persistence and unit tests.
