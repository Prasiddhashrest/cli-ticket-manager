"""SQLite persistence layer for the ticket manager."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import Ticket


class TicketRepository:
    """Create, retrieve, filter, and update tickets in SQLite."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
                    category TEXT NOT NULL CHECK(category IN
                        ('hardware', 'software', 'network', 'access', 'other')),
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open', 'resolved')),
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )

    @staticmethod
    def _to_ticket(row: sqlite3.Row) -> Ticket:
        return Ticket(**dict(row))

    def add(self, title: str, description: str, priority: str, category: str) -> Ticket:
        if not title.strip():
            raise ValueError("Ticket title cannot be empty.")
        if priority not in {"low", "medium", "high"}:
            raise ValueError("Invalid priority.")
        if category not in {"hardware", "software", "network", "access", "other"}:
            raise ValueError("Invalid category.")

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets (title, description, priority, category, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title.strip(), description.strip(), priority, category, created_at),
            )
            ticket_id = cursor.lastrowid
        return self.get(ticket_id)

    def get(self, ticket_id: int) -> Optional[Ticket]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        return self._to_ticket(row) if row else None

    def list_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Ticket]:
        query = "SELECT * FROM tickets WHERE 1 = 1"
        parameters = []
        for name, value in (("status", status), ("priority", priority), ("category", category)):
            if value is not None:
                query += " AND {} = ?".format(name)
                parameters.append(value)
        query += " ORDER BY id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_ticket(row) for row in rows]

    def set_status(self, ticket_id: int, status: str) -> Optional[Ticket]:
        if status not in {"open", "resolved"}:
            raise ValueError("Invalid status.")
        if self.get(ticket_id) is None:
            return None
        resolved_at = (
            datetime.now(timezone.utc).isoformat(timespec="seconds")
            if status == "resolved" else None
        )
        with self._connect() as connection:
            connection.execute(
                "UPDATE tickets SET status = ?, resolved_at = ? WHERE id = ?",
                (status, resolved_at, ticket_id),
            )
        return self.get(ticket_id)

    def stats(self) -> Dict[str, int]:
        counts = {"open": 0, "resolved": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status"
            ).fetchall()
        for row in rows:
            counts[row["status"]] = row["count"]
        counts["total"] = counts["open"] + counts["resolved"]
        return counts
