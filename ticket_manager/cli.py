"""Command-line interface for the SQLite-backed IT support ticket manager."""

import argparse
from pathlib import Path
from typing import List, Optional

from .models import Ticket
from .storage import TicketRepository

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "tickets.db"
PRIORITIES = ("low", "medium", "high")
CATEGORIES = ("hardware", "software", "network", "access", "other")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-manager", description="Manage local IT support tickets with SQLite."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help="SQLite database path (default: data/tickets.db)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Create a new ticket")
    add.add_argument("--title", required=True, help="Short ticket summary")
    add.add_argument("--description", default="", help="Details about the issue")
    add.add_argument("--priority", choices=PRIORITIES, default="medium")
    add.add_argument("--category", choices=CATEGORIES, default="other")
    add.add_argument("--agent", help="Optional technician to assign this ticket to")

    listing = commands.add_parser("list", help="List tickets with optional filters")
    listing.add_argument("--status", choices=("open", "resolved"))
    listing.add_argument("--priority", choices=PRIORITIES)
    listing.add_argument("--category", choices=CATEGORIES)
    assigned_filter = listing.add_mutually_exclusive_group()
    assigned_filter.add_argument("--agent", help="Only tickets assigned to this technician")
    assigned_filter.add_argument("--unassigned", action="store_true", help="Only unassigned tickets")

    show = commands.add_parser("show", help="Display one ticket")
    show.add_argument("id", type=int)

    assign = commands.add_parser("assign", help="Assign or reassign a technician")
    assign.add_argument("id", type=int)
    assign.add_argument("--agent", required=True, help="Technician name")

    unassign = commands.add_parser("unassign", help="Clear the technician assignment")
    unassign.add_argument("id", type=int)

    resolve = commands.add_parser("resolve", help="Mark a ticket resolved")
    resolve.add_argument("id", type=int)
    reopen = commands.add_parser("reopen", help="Reopen a resolved ticket")
    reopen.add_argument("id", type=int)
    commands.add_parser("stats", help="Show ticket counts")
    return parser


def display_ticket(ticket: Ticket) -> None:
    print("Ticket #{}".format(ticket.id))
    print("  Title:       {}".format(ticket.title))
    print("  Description: {}".format(ticket.description or "(none)"))
    print("  Priority:    {}".format(ticket.priority))
    print("  Category:    {}".format(ticket.category))
    print("  Status:      {}".format(ticket.status))
    print("  Assigned to: {}".format(ticket.assigned_to or "Unassigned"))
    print("  Created:     {}".format(ticket.created_at))
    print("  Resolved:    {}".format(ticket.resolved_at or "—"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    repo = TicketRepository(args.db)

    if args.command == "add":
        try:
            ticket = repo.add(
                args.title, args.description, args.priority, args.category, args.agent
            )
        except ValueError as error:
            parser.error(str(error))
        print("Created ticket #{}: {}".format(ticket.id, ticket.title))
    elif args.command == "list":
        tickets = repo.list_tickets(
            args.status, args.priority, args.category, args.agent, args.unassigned
        )
        if not tickets:
            print("No matching tickets.")
        else:
            print("{:<5} {:<9} {:<8} {:<9} {:<18} {}".format(
                "ID", "STATUS", "PRIORITY", "CATEGORY", "ASSIGNED TO", "TITLE"
            ))
            print("-" * 92)
            for ticket in tickets:
                print("{:<5} {:<9} {:<8} {:<9} {:<18} {}".format(
                    ticket.id, ticket.status, ticket.priority, ticket.category,
                    (ticket.assigned_to or "Unassigned")[:18], ticket.title,
                ))
    elif args.command == "show":
        ticket = repo.get(args.id)
        if ticket is None:
            print("Ticket #{} was not found.".format(args.id))
            return 1
        display_ticket(ticket)
    elif args.command in ("assign", "unassign"):
        if args.command == "assign":
            try:
                cleaned = TicketRepository._clean_agent(args.agent, required=True)
                ticket = repo.set_assignee(args.id, cleaned)
            except ValueError as error:
                parser.error(str(error))
        else:
            ticket = repo.set_assignee(args.id, None)
        if ticket is None:
            print("Ticket #{} was not found.".format(args.id))
            return 1
        if ticket.assigned_to:
            print("Ticket #{} assigned to {}.".format(ticket.id, ticket.assigned_to))
        else:
            print("Ticket #{} is now unassigned.".format(ticket.id))
    elif args.command in ("resolve", "reopen"):
        desired_status = "resolved" if args.command == "resolve" else "open"
        current = repo.get(args.id)
        if current is None:
            print("Ticket #{} was not found.".format(args.id))
            return 1
        if current.status == desired_status:
            print("Ticket #{} is already {}.".format(args.id, desired_status))
        else:
            repo.set_status(args.id, desired_status)
            print("Ticket #{} is now {}.".format(args.id, desired_status))
    elif args.command == "stats":
        counts = repo.stats()
        print("Total: {} | Open: {} | Resolved: {}".format(
            counts["total"], counts["open"], counts["resolved"]
        ))
    return 0
