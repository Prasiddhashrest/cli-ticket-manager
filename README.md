# IT Support Ticket Manager — Python CLI + Streamlit Dashboard

A local IT support ticket management demo built with Python and SQLite. Create tickets, set priorities and categories, assign tickets to technicians, reopen or resolve them, and explore your workload in an interactive dashboard. **Both the CLI and dashboard read/write the same local SQLite database.**

**Tech stack:** Python 3.9+, SQLite (`sqlite3`), Python `dataclasses` and `argparse`, Streamlit, `unittest`, GitHub Actions.

## Features

- Create and view tickets, with title, description, priority and category.
- Assign, reassign and unassign technicians (from CLI or dashboard).
- Filter by ticket status, priority, category, assigned technician or unassigned tickets.
- Mark tickets resolved or reopen them; timestamps are stored in UTC.
- Dashboard displays summary metrics, category/priority charts, a technician workload chart, and a searchable ticket table.
- Export filtered tickets as CSV from the dashboard.
- Persistent SQLite database using parameterized SQL queries.
- Automatic **non-destructive migration** that adds `assigned_to` to databases created with v1.0.
- Automated unit tests for ticket operations, assignment, CLI commands and database migration.

## Run the dashboard

From the project directory on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

Streamlit should open a local URL such as http://localhost:8501. Use **Control+C** to stop the server. When you return later, activate the virtual environment again with `source .venv/bin/activate`.

## CLI examples

```bash
# Use python (inside the venv), or python3 if your global Python is configured.
python main.py --help
python main.py add --title "VPN won't connect" --priority high --category network
python main.py add --title "Laptop replacement" --priority medium --category hardware --agent "Alex Kim"
python main.py list
python main.py list --unassigned
python main.py list --agent "Alex Kim"
python main.py assign 1 --agent "Taylor Lee"
python main.py show 1
python main.py unassign 1
python main.py resolve 1
python main.py reopen 1
python main.py stats
```

**Note:** `--db` is a global option and must come before the command. For example:

```bash
python main.py --db /tmp/demo-tickets.db list
```

## How upgrades preserve earlier tickets

The database is stored at `data/tickets.db` and deliberately excluded from Git. When a `TicketRepository` opens a v1.0 database, it checks existing SQLite columns with `PRAGMA table_info(tickets)`. If `assigned_to` is missing, it executes `ALTER TABLE tickets ADD COLUMN assigned_to TEXT`. Old tickets remain intact and start out unassigned (`NULL`). Running the migration a second time makes no change.

Before applying an upgrade to a database you care about, make a local backup:

```bash
if [ -f data/tickets.db ]; then cp data/tickets.db data/tickets-backup-before-v1.2.db; fi
```

The `data/` folder and `.venv/` are ignored by Git. Do not upload real support requests, passwords, employer details, or other confidential information to this demo app.

## Test

```bash
python -m unittest discover -s tests -v
```

The included GitHub Actions workflow automatically runs the standard-library tests on pushes and pull requests. No Streamlit installation is needed for those repository tests. The Streamlit user interface should also be tested manually in a browser.

## Folder structure

```text
cli-ticket-manager/
├── dashboard.py                # Visual UI: filters, charts, assignments
├── main.py                     # CLI entry point
├── requirements.txt            # Streamlit dependency
├── ticket_manager/
│   ├── __init__.py
│   ├── cli.py                  # argparse commands: add/list/assign/etc.
│   ├── models.py               # Immutable Ticket object
│   └── storage.py              # SQLite queries and schema migration
├── tests/
│   ├── test_ticket_manager.py  # Original regression tests
│   └── test_assignments.py     # New assignment + migration tests
├── .github/workflows/tests.yml
├── .gitignore
├── CHANGELOG.md
└── README.md
```

`data/tickets.db` is created on first run, not committed.

## Git workflow

Develop on a feature branch, test it, push the branch, open a pull request on GitHub, and merge after review. For example:

```bash
git status
python -m unittest discover -s tests -v
git add dashboard.py ticket_manager/models.py ticket_manager/storage.py ticket_manager/cli.py tests/test_assignments.py README.md CHANGELOG.md
git commit -m "Add technician assignment and workload analytics"
git push -u origin feature/visual-dashboard
```

Then open a pull request targeting `main` from `feature/visual-dashboard`. If using GitHub CLI (`gh`), `gh pr create --base main --head feature/visual-dashboard` starts the process. After merging, update your local main with `git switch main && git pull origin main`.

## Architecture at a glance

`main.py -> ticket_manager.cli -> TicketRepository -> SQLite`

`dashboard.py -> TicketRepository -> SQLite`

All new tickets are examples: this is a portfolio/learning app, not a production help-desk product. The development process demonstrates data modeling, SQL migrations, unit testing, UI design, and version control.
