# CLI Ticket Manager (Python + SQLite)

A command-line application for managing mock IT help-desk tickets. Create, inspect, filter, resolve, and reopen tickets, with data saved between runs in SQLite.

**Tech stack:** Python 3.9+, SQLite (`sqlite3`), `argparse`, `dataclasses`, `unittest`, GitHub Actions. No third-party dependencies.

## Features

- Create tickets with a title, description, priority, and category.
- List and filter tickets by status, priority, or category.
- View full ticket details.
- Resolve and reopen tickets with UTC timestamps.
- View total/open/resolved counts.
- Persistent SQLite database; parameterized SQL queries.
- Automated tests using Python's standard library.
- GitHub Actions runs the test suite for each push and pull request.

## Get started

From the project directory:

```bash
python3 --version
python3 main.py --help
python3 main.py add --title "VPN will not connect" --description "VPN fails after login" --priority high --category network
python3 main.py add --title "New employee access" --priority medium --category access
python3 main.py list
python3 main.py list --status open --priority high
python3 main.py show 1
python3 main.py resolve 1
python3 main.py list --status resolved
python3 main.py reopen 1
python3 main.py stats
```

By default, the database file is saved in `data/tickets.db` relative to the project, which is excluded from Git by `.gitignore`.

To use another database:

```bash
python3 main.py --db /tmp/demo-tickets.db list
```

**Note:** `--db` is a global option and must come before the subcommand.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Folder structure

```text
cli-ticket-manager/
├── main.py                   # Entrypoint
├── ticket_manager/
│   ├── __init__.py
│   ├── models.py             # Ticket data model
│   ├── storage.py            # SQLite repository
│   └── cli.py                # Argument parsing and output
├── tests/
│   ├── __init__.py
│   └── test_ticket_manager.py
├── .github/workflows/tests.yml # CI tests on GitHub
├── .gitignore
└── README.md
```

The `data/` directory is created automatically when you run a command. Keep the local DB out of Git.

## Design overview

`main.py` calls `ticket_manager.cli.main()`. The CLI parses the command and calls a `TicketRepository`. The repository executes parameterized SQL against SQLite and returns immutable `Ticket` objects.

## Future improvements

- Assignment of tickets to support agents.
- Search by keywords and date ranges.
- CSV export and import.
- Priority-based statistics or SLA tracking.
- Publish as a `pip`-installable command.

## Important note

This is a local learning/demo project using mock support tickets, not a production-ready help-desk system. Avoid entering actual passwords, customer records, or confidential work information.

## Push to GitHub

```bash
git init -b main
git add .
git commit -m "Build CLI ticket manager with SQLite"
gh auth login   # Only if you are not already logged in
gh repo create cli-ticket-manager --public --source=. --remote=origin --push
```

`gh` is GitHub's command-line app. If you don't have it, create an empty repository named `cli-ticket-manager` on GitHub and run:

```bash
git remote add origin https://github.com/YOUR_USERNAME/cli-ticket-manager.git
git push -u origin main
```

When using the website approach, don't check the option to generate a README because this repository already has one.
