"""v1.3 tests for editing, events, upgrades, and CLI workflows."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ticket_manager.cli import main
from ticket_manager.storage import TicketRepository


class EditAndHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "tickets.db"
        self.repo = TicketRepository(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_new_ticket_records_creation(self):
        ticket = self.repo.add("Password reset", "can't login", "high", "access")
        events = self.repo.list_events(ticket.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "created")
        self.assertEqual(events[0].new_value, "Password reset")
        self.assertIsNotNone(ticket.updated_at)

    def test_created_assigned_ticket_records_both(self):
        ticket = self.repo.add("VPN", "", "high", "network", "Jamie")
        self.assertEqual(
            [event.event_type for event in self.repo.list_events(ticket.id)],
            ["assigned", "created"],
        )

    def test_edit_all_fields_and_keep_old_values(self):
        ticket = self.repo.add("Printer", "Jammed", "low", "hardware")
        after = self.repo.update_ticket(
            ticket.id,
            title="Printer jam",
            description="Out of paper",
            priority="high",
            category="other",
        )
        self.assertEqual(after.title, "Printer jam")
        self.assertEqual(after.description, "Out of paper")
        self.assertEqual(after.priority, "high")
        self.assertEqual(after.category, "other")
        edited = [e for e in self.repo.list_events(ticket.id) if e.event_type == "edited"]
        self.assertEqual(len(edited), 4)
        values = {event.field_name: (event.old_value, event.new_value) for event in edited}
        self.assertEqual(values["title"], ("Printer", "Printer jam"))
        self.assertEqual(values["description"], ("Jammed", "Out of paper"))

    def test_edit_only_one_field_leaves_other_fields_untouched(self):
        ticket = self.repo.add("VPN", "Help", "low", "network")
        after = self.repo.update_ticket(ticket.id, priority="medium")
        self.assertEqual((after.title, after.description, after.category), ("VPN", "Help", "network"))
        self.assertEqual(len(self.repo.list_events(ticket.id)), 2)

    def test_clear_description_with_empty_string(self):
        ticket = self.repo.add("Monitor", "Old details", "medium", "hardware")
        after = self.repo.update_ticket(ticket.id, description="")
        self.assertEqual(after.description, "")
        self.assertEqual(self.repo.list_events(ticket.id)[0].old_value, "Old details")

    def test_repeating_identical_edit_creates_no_extra_activity(self):
        ticket = self.repo.add("VPN", "details", "high", "network")
        original_updated_at = ticket.updated_at
        self.repo.update_ticket(ticket.id, title="VPN", priority="high")
        self.assertEqual(len(self.repo.list_events(ticket.id)), 1)
        self.assertEqual(self.repo.get(ticket.id).updated_at, original_updated_at)

    def test_repeating_identical_assignment_and_status_creates_no_events(self):
        ticket = self.repo.add("Wi-Fi", "", "low", "network")
        self.repo.set_assignee(ticket.id, "Taylor")
        self.repo.set_assignee(ticket.id, "Taylor")
        self.repo.set_status(ticket.id, "resolved")
        resolved_at = self.repo.get(ticket.id).resolved_at
        self.repo.set_status(ticket.id, "resolved")
        self.assertEqual(len(self.repo.list_events(ticket.id)), 3)
        self.assertEqual(self.repo.get(ticket.id).resolved_at, resolved_at)

    def test_assignment_and_status_changes_audited(self):
        ticket = self.repo.add("VPN", "", "high", "network", "Jamie")
        self.repo.set_assignee(ticket.id, "Taylor")
        self.repo.set_assignee(ticket.id, None)
        self.repo.set_status(ticket.id, "resolved")
        self.repo.set_status(ticket.id, "open")
        events = self.repo.list_events(ticket.id)
        self.assertEqual([e.event_type for e in events[:4]],
                         ["status_changed", "status_changed", "assigned", "assigned"])
        self.assertEqual((events[0].old_value, events[0].new_value), ("resolved", "open"))
        self.assertEqual((events[2].old_value, events[2].new_value), ("Taylor", None))

    def test_missing_ticket_no_phantom_changes(self):
        self.assertIsNone(self.repo.update_ticket(999, title="Gone"))
        self.assertIsNone(self.repo.set_assignee(999, "Alex"))
        self.assertIsNone(self.repo.set_status(999, "resolved"))
        self.assertEqual(self.repo.list_events(), [])

    def test_validation_rollback_preserves_ticket_and_events(self):
        ticket = self.repo.add("Database", "", "medium", "software")
        before = self.repo.list_events(ticket.id)
        for changes in (
            {"title": "   "},
            {"title": "x" * 151},
            {"description": "a" * 5001},
            {"priority": "urgent"},
            {"category": "unknown"},
            {},
        ):
            with self.assertRaises(ValueError):
                self.repo.update_ticket(ticket.id, **changes)
        self.assertEqual(self.repo.get(ticket.id).title, "Database")
        self.assertEqual(self.repo.list_events(ticket.id), before)

    def test_sql_injection_title_is_just_text(self):
        ticket = self.repo.add("Printer", "", "low", "hardware")
        attack = "VPN', status='resolved' --"
        after = self.repo.update_ticket(ticket.id, title=attack)
        self.assertEqual(after.title, attack)
        self.assertEqual(after.status, "open")

    def test_events_persist_and_global_feed_is_newest_first(self):
        first = self.repo.add("First", "", "low", "other")
        second = self.repo.add("Second", "", "low", "other")
        self.repo.update_ticket(first.id, title="Updated")
        reopened = TicketRepository(self.path)
        self.assertEqual(reopened.list_events(limit=1)[0].ticket_id, first.id)
        self.assertEqual(len(reopened.list_events(second.id)), 1)
        with self.assertRaises(ValueError):
            self.repo.list_events(limit=0)
        with self.assertRaises(ValueError):
            self.repo.list_events(limit=501)

    def test_cli_edit_and_history(self):
        ticket = self.repo.add("VPN", "", "high", "network")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--db", str(self.path), "edit", str(ticket.id),
                                   "--title", "VPN fixed", "--priority", "medium"]), 0)
            self.assertEqual(main(["--db", str(self.path), "history", str(ticket.id)]), 0)
            self.assertEqual(main(["--db", str(self.path), "activity", "--limit", "2"]), 0)
        self.assertIn("VPN fixed", output.getvalue())
        self.assertIn("edited / title", output.getvalue())

    def test_cli_missing_id_and_empty_edit(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--db", str(self.path), "edit", "500", "--title", "Hi"]), 1)
            self.assertEqual(main(["--db", str(self.path), "history", "500"]), 1)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--db", str(self.path), "edit", "1"])
        self.assertEqual(caught.exception.code, 2)

    def test_migration_from_v12_keeps_records_and_prior_work_history_empty(self):
        legacy = Path(self.directory.name) / "legacy-v12.db"
        with sqlite3.connect(str(legacy)) as conn:
            conn.execute("""CREATE TABLE tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL, category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
                resolved_at TEXT, assigned_to TEXT
            )""")
            conn.execute("""INSERT INTO tickets
                (title, description, priority, category, status, created_at, assigned_to)
                VALUES ('Existing VPN', 'Old entry', 'high', 'network', 'open', '2026-04-01', 'Alex')
            """)
        upgraded = TicketRepository(legacy)
        original = upgraded.get(1)
        self.assertEqual(original.assigned_to, "Alex")
        self.assertIsNone(original.updated_at)
        self.assertEqual(upgraded.list_events(ticket_id=1), [])
        upgraded.update_ticket(1, description="Investigating")
        self.assertEqual(len(upgraded.list_events(ticket_id=1)), 1)
        # Reopening the repository reruns migrations safely.
        self.assertEqual(TicketRepository(legacy).get(1).description, "Investigating")


if __name__ == "__main__":
    unittest.main()
