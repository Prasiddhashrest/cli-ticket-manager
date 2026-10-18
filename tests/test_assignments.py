"""Regression tests for technician assignment and legacy SQLite migration."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ticket_manager.cli import main
from ticket_manager.storage import TicketRepository


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Path(self.temp_dir.name) / "tickets.db"
        self.repo = TicketRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_tickets_start_unassigned(self):
        ticket = self.repo.add("VPN trouble", "", "high", "network")
        self.assertIsNone(ticket.assigned_to)

    def test_create_ticket_with_technician(self):
        ticket = self.repo.add("Software install", "", "medium", "software", "  Alex Kim  ")
        self.assertEqual(ticket.assigned_to, "Alex Kim")
        self.assertEqual(TicketRepository(self.db).get(ticket.id).assigned_to, "Alex Kim")

    def test_assign_and_reassign(self):
        ticket = self.repo.add("Printer", "", "low", "hardware")
        self.assertEqual(self.repo.set_assignee(ticket.id, "Taylor").assigned_to, "Taylor")
        self.assertEqual(self.repo.set_assignee(ticket.id, "Jordan").assigned_to, "Jordan")
        self.assertEqual(self.repo.get(ticket.id).assigned_to, "Jordan")

    def test_unassign(self):
        ticket = self.repo.add("Wi-Fi", "", "high", "network", "Taylor")
        self.assertIsNone(self.repo.set_assignee(ticket.id, None).assigned_to)
        self.assertIsNone(self.repo.get(ticket.id).assigned_to)

    def test_filter_by_technician_and_unassigned(self):
        self.repo.add("VPN", "", "high", "network", "Taylor")
        self.repo.add("Monitor", "", "low", "hardware", "Jordan")
        self.repo.add("Printer", "", "medium", "hardware")
        self.assertEqual(len(self.repo.list_tickets(assigned_to="taylor")), 1)
        self.assertEqual(len(self.repo.list_tickets(unassigned=True)), 1)
        self.assertEqual(len(self.repo.list_tickets(priority="high", assigned_to="Taylor")), 1)
        with self.assertRaises(ValueError):
            self.repo.list_tickets(assigned_to="Taylor", unassigned=True)

    def test_missing_ticket_returns_none(self):
        self.assertIsNone(self.repo.set_assignee(999, "Jordan"))
        self.assertIsNone(self.repo.set_assignee(999, None))

    def test_reject_long_technician(self):
        with self.assertRaises(ValueError):
            self.repo.add("VPN", "", "high", "network", "x" * 81)
        with self.assertRaises(ValueError):
            self.repo.set_assignee(1, "x" * 81)

    def test_cli_assignment_and_filter(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--db", str(self.db), "add", "--title", "Printer"]), 0)
            self.assertEqual(main(["--db", str(self.db), "assign", "1", "--agent", "Jordan"]), 0)
            self.assertEqual(main(["--db", str(self.db), "list", "--agent", "Jordan"]), 0)
            self.assertEqual(main(["--db", str(self.db), "unassign", "1"]), 0)
            self.assertEqual(main(["--db", str(self.db), "list", "--unassigned"]), 0)
        output_text = output.getvalue()
        self.assertIn("assigned to Jordan", output_text)
        self.assertIn("now unassigned", output_text)
        self.assertIn("Printer", output_text)

    def test_cli_rejects_empty_technician(self):
        with redirect_stdout(io.StringIO()):
            self.repo.add("Printer", "", "medium", "other")
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--db", str(self.db), "assign", "1", "--agent", "  "])
        self.assertEqual(caught.exception.code, 2)

    def test_legacy_database_migrates_and_preserves_ticket(self):
        # Simulate the previous version's DB without assigned_to.
        legacy_db = Path(self.temp_dir.name) / "legacy.db"
        with sqlite3.connect(str(legacy_db)) as connection:
            connection.execute("""
                CREATE TABLE tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)
            connection.execute("""
                INSERT INTO tickets
                    (title, description, priority, category, status, created_at)
                VALUES ('Old printer issue', '', 'low', 'hardware', 'open', '2026-01-01')
            """)

        updated_repo = TicketRepository(legacy_db)
        ticket = updated_repo.get(1)
        self.assertEqual(ticket.title, "Old printer issue")
        self.assertIsNone(ticket.assigned_to)
        updated_repo.set_assignee(1, "Taylor")
        self.assertEqual(TicketRepository(legacy_db).get(1).assigned_to, "Taylor")


if __name__ == "__main__":
    unittest.main()
