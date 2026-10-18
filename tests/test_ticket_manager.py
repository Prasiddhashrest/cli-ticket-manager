"""Run with: python3 -m unittest discover -s tests -v"""

import tempfile
import unittest
from pathlib import Path

from ticket_manager.storage import TicketRepository


class TicketManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Path(self.temp_dir.name) / "tickets.db"
        self.repo = TicketRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_read_ticket(self):
        ticket = self.repo.add("Wi-Fi down", "Cannot connect", "high", "network")
        self.assertEqual(ticket.id, 1)
        self.assertEqual(ticket.status, "open")
        self.assertEqual(self.repo.get(1).title, "Wi-Fi down")
        self.assertTrue(self.db.exists())

    def test_filter_tickets(self):
        self.repo.add("VPN", "", "high", "network")
        self.repo.add("Printer", "", "low", "hardware")
        tickets = self.repo.list_tickets(priority="high", category="network")
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0].title, "VPN")

    def test_resolve_and_reopen(self):
        ticket = self.repo.add("Reset password", "", "medium", "access")
        resolved = self.repo.set_status(ticket.id, "resolved")
        self.assertEqual(resolved.status, "resolved")
        self.assertIsNotNone(resolved.resolved_at)
        reopened = self.repo.set_status(ticket.id, "open")
        self.assertEqual(reopened.status, "open")
        self.assertIsNone(reopened.resolved_at)

    def test_database_persists_between_instances(self):
        self.repo.add("Laptop issue", "", "low", "hardware")
        another_repo = TicketRepository(self.db)
        self.assertEqual(another_repo.get(1).title, "Laptop issue")

    def test_status_counts(self):
        first = self.repo.add("App crash", "", "high", "software")
        self.repo.add("Monitor", "", "low", "hardware")
        self.repo.set_status(first.id, "resolved")
        self.assertEqual(self.repo.stats(), {"open": 1, "resolved": 1, "total": 2})

    def test_reject_empty_title(self):
        with self.assertRaises(ValueError):
            self.repo.add("   ", "", "low", "other")

    def test_missing_ticket(self):
        self.assertIsNone(self.repo.get(999))
        self.assertIsNone(self.repo.set_status(999, "resolved"))


if __name__ == "__main__":
    unittest.main()
