"""SQLite persistence, safe schema migrations, and append-only ticket activity."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import Ticket, TicketEvent


class TicketRepository:
    """Persist tickets and their history in a single local SQLite database."""

    PRIORITIES = {"low", "medium", "high"}
    CATEGORIES = {"hardware", "software", "network", "access", "other"}

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(str(self.database_path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

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
                    resolved_at TEXT,
                    assigned_to TEXT,
                    updated_at TEXT
                )
                """
            )
            # Migrations support both v1.0 (no assignee) and v1.2 databases.
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tickets)")
            }
            if "assigned_to" not in columns:
                connection.execute("ALTER TABLE tickets ADD COLUMN assigned_to TEXT")
            if "updated_at" not in columns:
                connection.execute("ALTER TABLE tickets ADD COLUMN updated_at TEXT")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ticket_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                    event_type TEXT NOT NULL,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id "
                "ON ticket_events(ticket_id, id DESC)"
            )

    @staticmethod
    def _to_ticket(row: sqlite3.Row) -> Ticket:
        return Ticket(**dict(row))

    @staticmethod
    def _to_event(row: sqlite3.Row) -> TicketEvent:
        return TicketEvent(**dict(row))

    @staticmethod
    def _clean_agent(agent: Optional[str], *, required: bool = False) -> Optional[str]:
        cleaned = agent.strip() if agent is not None else ""
        if required and not cleaned:
            raise ValueError("Technician name cannot be empty.")
        if len(cleaned) > 80:
            raise ValueError("Technician name must be 80 characters or fewer.")
        return cleaned or None

    @classmethod
    def _clean_fields(cls, fields: dict) -> dict:
        """Validate only supplied editable fields; None means 'not provided'."""
        cleaned = {}
        for name, value in fields.items():
            if value is None:
                continue
            value = value.strip()
            if name == "title":
                if not value:
                    raise ValueError("Ticket title cannot be empty.")
                if len(value) > 150:
                    raise ValueError("Ticket title must be 150 characters or fewer.")
            elif name == "description":
                if len(value) > 5000:
                    raise ValueError("Description must be 5000 characters or fewer.")
            elif name == "priority":
                if value not in cls.PRIORITIES:
                    raise ValueError("Invalid priority.")
            elif name == "category":
                if value not in cls.CATEGORIES:
                    raise ValueError("Invalid category.")
            else:
                raise ValueError("This ticket field cannot be edited.")
            cleaned[name] = value
        return cleaned

    @staticmethod
    def _log_event(connection, ticket_id, event_type, field_name, old_value, new_value, at):
        connection.execute(
            """
            INSERT INTO ticket_events
              (ticket_id, event_type, field_name, old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, event_type, field_name, old_value, new_value, at),
        )

    def add(
        self,
        title: str,
        description: str,
        priority: str,
        category: str,
        assigned_to: Optional[str] = None,
    ) -> Ticket:
        fields = self._clean_fields(dict(
            title=title, description=description, priority=priority, category=category
        ))
        agent = self._clean_agent(assigned_to)
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets
                    (title, description, priority, category, created_at, assigned_to, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (fields["title"], fields["description"], fields["priority"],
                 fields["category"], now, agent, now),
            )
            ticket_id = cursor.lastrowid
            self._log_event(connection, ticket_id, "created", "title", None, fields["title"], now)
            if agent is not None:
                self._log_event(connection, ticket_id, "assigned", "assigned_to", None, agent, now)
        return self.get(ticket_id)

    def get(self, ticket_id: int) -> Optional[Ticket]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._to_ticket(row) if row else None

    def list_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        assigned_to: Optional[str] = None,
        unassigned: bool = False,
    ) -> List[Ticket]:
        if unassigned and assigned_to is not None:
            raise ValueError("Choose either a technician filter or unassigned.")
        query = "SELECT * FROM tickets WHERE 1 = 1"
        parameters = []
        for name, value in (("status", status), ("priority", priority), ("category", category)):
            if value is not None:
                query += " AND {} = ?".format(name)  # Column names come from this fixed tuple.
                parameters.append(value)
        if assigned_to is not None:
            query += " AND assigned_to = ? COLLATE NOCASE"
            parameters.append(self._clean_agent(assigned_to, required=True))
        elif unassigned:
            query += " AND assigned_to IS NULL"
        query += " ORDER BY id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_ticket(row) for row in rows]

    def update_ticket(
        self,
        ticket_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[Ticket]:
        """Edit fields and record each real change atomically. None skips a field."""
        cleaned = self._clean_fields(dict(
            title=title, description=description, priority=priority, category=category
        ))
        if not cleaned:
            raise ValueError("Provide at least one field to edit.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            before = connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
            if before is None:
                return None
            changes = {name: value for name, value in cleaned.items() if before[name] != value}
            if changes:
                now = self._now()
                # Only keys validated by _clean_fields become SQL column names.
                set_clause = ", ".join("{} = ?".format(name) for name in changes)
                connection.execute(
                    "UPDATE tickets SET {}, updated_at = ? WHERE id = ?".format(set_clause),
                    (*changes.values(), now, ticket_id),
                )
                for name, new_value in changes.items():
                    self._log_event(connection, ticket_id, "edited", name, before[name], new_value, now)
        return self.get(ticket_id)

    def set_assignee(self, ticket_id: int, assigned_to: Optional[str]) -> Optional[Ticket]:
        agent = self._clean_agent(assigned_to)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            before = connection.execute(
                "SELECT assigned_to FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
            if before is None:
                return None
            if before["assigned_to"] != agent:
                now = self._now()
                connection.execute(
                    "UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?",
                    (agent, now, ticket_id),
                )
                self._log_event(
                    connection, ticket_id, "assigned", "assigned_to", before["assigned_to"], agent, now
                )
        return self.get(ticket_id)

    def set_status(self, ticket_id: int, status: str) -> Optional[Ticket]:
        if status not in {"open", "resolved"}:
            raise ValueError("Invalid status.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            before = connection.execute(
                "SELECT status FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
            if before is None:
                return None
            if before["status"] != status:
                now = self._now()
                resolved_at = now if status == "resolved" else None
                connection.execute(
                    "UPDATE tickets SET status = ?, resolved_at = ?, updated_at = ? WHERE id = ?",
                    (status, resolved_at, now, ticket_id),
                )
                self._log_event(
                    connection, ticket_id, "status_changed", "status", before["status"], status, now
                )
        return self.get(ticket_id)

    def list_events(self, ticket_id: Optional[int] = None, limit: int = 100) -> List[TicketEvent]:
        if not 1 <= limit <= 500:
            raise ValueError("Limit must be between 1 and 500.")
        query = "SELECT * FROM ticket_events"
        args = []
        if ticket_id is not None:
            query += " WHERE ticket_id = ?"
            args.append(ticket_id)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [self._to_event(row) for row in rows]

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
