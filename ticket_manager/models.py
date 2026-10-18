"""Immutable domain models for IT support tickets and activity history."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Ticket:
    id: int
    title: str
    description: str
    priority: str
    category: str
    status: str
    created_at: str
    resolved_at: Optional[str] = None
    assigned_to: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class TicketEvent:
    id: int
    ticket_id: int
    event_type: str
    field_name: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    created_at: str
