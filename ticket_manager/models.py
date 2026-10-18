"""Domain model for IT support tickets."""

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
