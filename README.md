# Support Desk — Python IT Ticket Manager (v1.3)

A local software engineering portfolio project featuring both a Python command-line interface and a browser-based Streamlit dashboard. Both interfaces share one SQLite database, so changes made in the terminal immediately appear in the web dashboard.

**Stack:** Python 3.9+, SQLite (`sqlite3`), OOP and Python dataclasses, `argparse`, Streamlit, Python `unittest`, GitHub Actions.

## Features

- Create, view, filter, and resolve/reopen mock IT support tickets.
- Assign, reassign, and unassign technicians.
- **Edit title, description, priority, and category** of existing tickets.
- **Activity history** records ticket creations and any new edits, assignment changes, and status changes, with old/new values and UTC timestamps.
- Visual dashboard with searchable queue, status metrics, ticket trends, workload charts, individual ticket history, and a global activity log.
- Download filtered tickets to CSV.
- Durable local storage and parameterized SQLite queries.
- Automated regression tests and backward-compatible database migrations.

## Run locally

```bash
cd ~/Downloads/cli-ticket-manager
python3 -m venv .venv                  # Only if your venv doesn't already exist
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

Open the displayed local URL (normally http://localhost:8501). Press Control+C to stop the server. Your local database is stored in `data/tickets.db`.

### Browser navigation

- **Overview:** KPIs, category/priority charts, creation trends, and the searchable queue.
- **Manage tickets:** Select a ticket, edit details, assign a technician, resolve or reopen it, and inspect its history. Filters in the sidebar affect the queue in both Overview and Manage tickets.
- **New ticket:** Submit mock support requests.
- **Activity log:** See recorded changes across tickets or filter the log to one ticket.

## CLI examples

```bash
python main.py --help
python main.py add --title "VPN connection issue" --priority high --category network
python main.py list
python main.py show 1
python main.py edit 1 --title "VPN fails when remote" --priority medium
python main.py edit 1 --description ""    # Clear the description
python main.py assign 1 --agent "Taylor Lee"
python main.py resolve 1
python main.py history 1
python main.py activity --limit 20
python main.py reopen 1
```

To use a test database instead, place `--db /path/to/database.db` **before** the command.

## Upgrading from earlier versions

Before unzipping an update into an existing project, stop Streamlit and back up the local database:

```bash
mkdir -p backups
if [ -f data/tickets.db ]; then cp data/tickets.db backups/tickets-before-v1.3.db; fi
```

On first run, `TicketRepository` performs a repeatable SQLite migration:

- Adds the `assigned_to` column if upgrading directly from v1.0.
- Adds an optional `updated_at` timestamp column.
- Creates a separate `ticket_events` table for event history.
- Preserves all existing ticket rows.

**Important:** This migration cannot reconstruct events from previous releases. An older ticket's activity will be empty until you modify it after installing v1.3. An old ticket with `updated_at = NULL` has no recorded modification timestamp yet.

Local tickets, `.venv`, and backups are ignored by Git via `.gitignore` patterns. Don't include personal information, real passwords, or confidential employer support requests in this learning project. This is a single-user demo, not a production help-desk solution or tamper-proof audit service.

## Run automated tests

```bash
python -m unittest discover -s tests -v
```

The repository's GitHub Actions workflow runs standard-library tests on pushes and pull requests. Test the interactive UI manually in your browser after updating.

## Recommended Git feature-branch workflow

```bash
git switch main
git pull origin main
git switch -c feature/ticket-edit-history-v1.3
# Unzip the v1.3 overlay into the root of the repo.
python -m unittest discover -s tests -v
git status
git diff --stat
git add dashboard.py ticket_manager/models.py ticket_manager/storage.py ticket_manager/cli.py tests/test_edit_history.py README.md CHANGELOG.md
git commit -m "Add ticket editing and activity history"
git push -u origin feature/ticket-edit-history-v1.3
# Create a PR with: gh pr create --base main --head feature/ticket-edit-history-v1.3 --fill
```

## Architecture

```text
main.py ──────> ticket_manager/cli.py ─┐
                                      ├──> TicketRepository ──> SQLite
 dashboard.py ────────────────────────┘          |
                                                ├── tickets (current state)
                                                └── ticket_events (recorded changes)
```

History events are stored inside the same SQLite transaction as their associated ticket update. When no field actually changes, no event is added.
