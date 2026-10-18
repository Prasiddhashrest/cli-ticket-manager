"""Streamlit dashboard for the IT Ticket Manager.

Run from the project root:
    python -m streamlit run dashboard.py

Uses the same SQLite database as the CLI, including an in-place schema upgrade
for previously created tickets.
"""

import csv
from collections import Counter
from dataclasses import asdict
from io import StringIO

import streamlit as st

from ticket_manager.cli import CATEGORIES, DEFAULT_DB, PRIORITIES
from ticket_manager.storage import TicketRepository


st.set_page_config(
    page_title="IT Support | Ticket Manager",
    page_icon="🎫",
    layout="wide",
)

repo = TicketRepository(DEFAULT_DB)
all_tickets = repo.list_tickets()

st.title("🎫 IT Support Ticket Manager")
st.caption("Interactive Python + SQLite dashboard | Runs locally on your computer")

message = st.session_state.pop("message", None)
if message:
    st.success(message)

# Names already in your database become available as filter options.
known_agents = sorted({ticket.assigned_to for ticket in all_tickets if ticket.assigned_to}, key=str.casefold)
with st.sidebar:
    st.header("🔎 Filter tickets")
    search = st.text_input("Search", placeholder="Search title or description...")
    status_filter = st.selectbox("Status", ("all", "open", "resolved"))
    priority_filter = st.selectbox("Priority", ("all",) + PRIORITIES)
    category_filter = st.selectbox("Category", ("all",) + CATEGORIES)
    agent_filter = st.selectbox(
        "Technician",
        (None, "") + tuple(known_agents),
        format_func=lambda name: (
            "All technicians" if name is None else "Unassigned" if name == "" else name
        ),
    )
    st.divider()
    st.caption("Your data stays in data/tickets.db on this computer")


def matches_filters(ticket):
    text = search.strip().casefold()
    matches_agent = (
        agent_filter is None
        or (agent_filter == "" and ticket.assigned_to is None)
        or (ticket.assigned_to is not None and ticket.assigned_to == agent_filter)
    )
    return (
        (not text or text in ticket.title.casefold() or text in ticket.description.casefold())
        and (status_filter == "all" or ticket.status == status_filter)
        and (priority_filter == "all" or ticket.priority == priority_filter)
        and (category_filter == "all" or ticket.category == category_filter)
        and matches_agent
    )


filtered_tickets = [ticket for ticket in all_tickets if matches_filters(ticket)]
dashboard_tab, new_ticket_tab = st.tabs(("📊 Dashboard", "➕ New ticket"))

with dashboard_tab:
    total = len(all_tickets)
    open_count = sum(ticket.status == "open" for ticket in all_tickets)
    resolved_count = total - open_count
    urgent_open = sum(t.status == "open" and t.priority == "high" for t in all_tickets)
    unassigned_open = sum(t.status == "open" and not t.assigned_to for t in all_tickets)

    first, second, third, fourth, fifth = st.columns(5)
    first.metric("Total tickets", total)
    second.metric("Open", open_count)
    third.metric("Resolved", resolved_count)
    fourth.metric("High-priority open", urgent_open)
    fifth.metric("Unassigned open", unassigned_open)

    st.divider()
    st.subheader("Ticket activity")
    st.caption("Charts and ticket table reflect the filters in the sidebar.")

    if filtered_tickets:
        categories = Counter(t.category for t in filtered_tickets)
        priorities = Counter(t.priority for t in filtered_tickets)
        workload = Counter(t.assigned_to or "Unassigned" for t in filtered_tickets)

        left, right = st.columns(2)
        with left:
            st.markdown("**Tickets by category**")
            st.bar_chart(
                [{"Category": c.title(), "Tickets": categories[c]} for c in CATEGORIES],
                x="Category", y="Tickets",
            )
        with right:
            st.markdown("**Tickets by priority**")
            st.bar_chart(
                [{"Priority": p.title(), "Tickets": priorities[p]} for p in PRIORITIES],
                x="Priority", y="Tickets",
            )
        st.markdown("**Workload by technician**")
        st.bar_chart(
            [{"Technician": name, "Tickets": count} for name, count in sorted(workload.items())],
            x="Technician", y="Tickets",
        )
    else:
        st.info("No matching tickets. Try changing the filters or creating a new ticket.")

    st.subheader(f"Tickets ({len(filtered_tickets)})")
    if filtered_tickets:
        columns = ("id", "title", "priority", "category", "status", "assigned_to", "created_at")
        st.dataframe(
            [
                {key: (getattr(t, key) if getattr(t, key) is not None else "Unassigned") for key in columns}
                for t in filtered_tickets
            ],
            hide_index=True,
            use_container_width=True,
        )

        selected_id = st.selectbox(
            "Choose a ticket to inspect or update",
            options=[t.id for t in filtered_tickets],
            format_func=lambda ticket_id: next(
                f"#{t.id}: {t.title} ({t.status})" for t in filtered_tickets if t.id == ticket_id
            ),
        )
        selected = repo.get(selected_id)
        if selected:
            with st.expander("Ticket details and actions", expanded=True):
                st.write(f"**Title:** {selected.title}")
                st.write(f"**Description:** {selected.description or '(none)'}")
                st.write(f"**Priority:** {selected.priority.title()}")
                st.write(f"**Category:** {selected.category.title()}")
                st.write(f"**Assigned to:** {selected.assigned_to or 'Unassigned'}")
                st.write(f"**Created:** {selected.created_at}")
                st.write(f"**Resolved:** {selected.resolved_at or 'Not yet resolved'}")

                st.markdown("**Assign or reassign**")
                with st.form(f"assignment_{selected.id}"):
                    technician = st.text_input(
                        "Technician name",
                        value=selected.assigned_to or "",
                        help="Enter a name to assign this ticket; use Unassign to clear it.",
                    )
                    assign_col, clear_col = st.columns(2)
                    save_assignment = assign_col.form_submit_button("Save technician", type="primary")
                    clear_assignment = clear_col.form_submit_button("Unassign")

                if save_assignment:
                    if not technician.strip():
                        st.error("Enter a technician name, or click Unassign.")
                    else:
                        try:
                            repo.set_assignee(selected.id, technician)
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state["message"] = f"Ticket #{selected.id} assigned to {technician.strip()}."
                            st.rerun()
                if clear_assignment:
                    repo.set_assignee(selected.id, None)
                    st.session_state["message"] = f"Ticket #{selected.id} is now unassigned."
                    st.rerun()

                st.markdown("**Change status**")
                action = "Resolve ticket" if selected.status == "open" else "Reopen ticket"
                new_status = "resolved" if selected.status == "open" else "open"
                if st.button(action, key=f"status_change_{selected.id}"):
                    repo.set_status(selected.id, new_status)
                    st.session_state["message"] = f"Ticket #{selected.id} is now {new_status}."
                    st.rerun()

        buffer = StringIO()
        export_fields = tuple(asdict(filtered_tickets[0]).keys())
        writer = csv.DictWriter(buffer, fieldnames=export_fields)
        writer.writeheader()
        for ticket in filtered_tickets:
            row = asdict(ticket)
            for field, value in row.items():
                # Prevent spreadsheet formula execution if a downloaded CSV is opened.
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[field] = "'" + value
            writer.writerow(row)
        st.download_button(
            "⬇️ Export filtered tickets to CSV",
            data=buffer.getvalue(),
            file_name="support_tickets.csv",
            mime="text/csv",
        )

with new_ticket_tab:
    st.subheader("Create an IT support ticket")
    with st.form("new_ticket", clear_on_submit=True):
        title = st.text_input("Issue title *", placeholder="Example: Laptop can't connect to Wi-Fi")
        description = st.text_area("Description", placeholder="Describe the problem...")
        left, right = st.columns(2)
        priority = left.selectbox("Priority", PRIORITIES, index=1)
        category = right.selectbox("Category", CATEGORIES)
        agent = st.text_input("Technician (optional)", placeholder="Example: Alex Kim")
        submitted = st.form_submit_button("Create ticket", type="primary")

    if submitted:
        try:
            created = repo.add(title, description, priority, category, agent)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["message"] = f"Created ticket #{created.id}: {created.title}"
            st.rerun()
