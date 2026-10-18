"""Interactive local web dashboard for the CLI Ticket Manager.

Run from the project folder with:
    python -m streamlit run dashboard.py

Both interfaces use the same SQLite database, so changes stay in sync.
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

# Save feedback across Streamlit reruns (which refresh the entire page).
message = st.session_state.pop("message", None)
if message:
    st.success(message)

with st.sidebar:
    st.header("🔎 Filter tickets")
    search = st.text_input("Search", placeholder="Search title or description...")
    status_filter = st.selectbox("Status", ("all", "open", "resolved"))
    priority_filter = st.selectbox("Priority", ("all",) + PRIORITIES)
    category_filter = st.selectbox("Category", ("all",) + CATEGORIES)
    st.divider()
    st.caption("Your data is stored locally in data/tickets.db")


def matches_filters(ticket):
    text = search.strip().casefold()
    return (
        (not text or text in ticket.title.casefold() or text in ticket.description.casefold())
        and (status_filter == "all" or ticket.status == status_filter)
        and (priority_filter == "all" or ticket.priority == priority_filter)
        and (category_filter == "all" or ticket.category == category_filter)
    )


filtered_tickets = [ticket for ticket in all_tickets if matches_filters(ticket)]

dashboard_tab, new_ticket_tab = st.tabs(("📊 Dashboard", "➕ New ticket"))

with dashboard_tab:
    total = len(all_tickets)
    open_count = sum(t.status == "open" for t in all_tickets)
    resolved_count = total - open_count
    urgent_open = sum(t.status == "open" and t.priority == "high" for t in all_tickets)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total tickets", total)
    col2.metric("Open", open_count)
    col3.metric("Resolved", resolved_count)
    col4.metric("High priority · open", urgent_open)

    st.divider()
    st.subheader("Ticket activity")
    st.caption("Charts and table reflect your search and filter selections.")

    if filtered_tickets:
        categories = Counter(t.category for t in filtered_tickets)
        priorities = Counter(t.priority for t in filtered_tickets)
        left, right = st.columns(2)
        with left:
            st.markdown("**Tickets by category**")
            st.bar_chart(
                [{"Category": c.title(), "Tickets": categories[c]} for c in CATEGORIES],
                x="Category",
                y="Tickets",
            )
        with right:
            st.markdown("**Tickets by priority**")
            st.bar_chart(
                [{"Priority": p.title(), "Tickets": priorities[p]} for p in PRIORITIES],
                x="Priority",
                y="Tickets",
            )
    else:
        st.info("No matching tickets yet. Try changing your filters or add a ticket.")

    st.subheader(f"Tickets ({len(filtered_tickets)})")
    if filtered_tickets:
        columns = ("id", "title", "priority", "category", "status", "created_at")
        st.dataframe(
            [{key: getattr(ticket, key) for key in columns} for ticket in filtered_tickets],
            hide_index=True,
            use_container_width=True,
        )

        selected_id = st.selectbox(
            "Choose a ticket to inspect or update",
            options=[t.id for t in filtered_tickets],
            format_func=lambda ticket_id: next(
                f"#{t.id}: {t.title} ({t.status})"
                for t in filtered_tickets
                if t.id == ticket_id
            ),
        )
        selected = repo.get(selected_id)
        if selected:
            with st.expander("Ticket details", expanded=True):
                st.write(f"**Title:** {selected.title}")
                st.write(f"**Description:** {selected.description or '(none)'}")
                st.write(f"**Priority:** {selected.priority.title()}")
                st.write(f"**Category:** {selected.category.title()}")
                st.write(f"**Created:** {selected.created_at}")
                st.write(f"**Resolved:** {selected.resolved_at or 'Not yet resolved'}")
                action = "Resolve ticket" if selected.status == "open" else "Reopen ticket"
                new_status = "resolved" if selected.status == "open" else "open"
                if st.button(action, type="primary", key="status_change"):
                    repo.set_status(selected.id, new_status)
                    st.session_state["message"] = f"Ticket #{selected.id} is now {new_status}."
                    st.rerun()

        # Standard library CSV output: no new dependency for exporting data.
        buffer = StringIO()
        export_fields = tuple(asdict(filtered_tickets[0]).keys())
        writer = csv.DictWriter(buffer, fieldnames=export_fields)
        writer.writeheader()
        for ticket in filtered_tickets:
            # Prefix potentially executable spreadsheet formulas to make exports safer
            # when somebody opens the CSV in Excel or similar spreadsheet software.
            row = asdict(ticket)
            for field, value in row.items():
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
        submitted = st.form_submit_button("Create ticket", type="primary")

    if submitted:
        try:
            created = repo.add(title, description, priority, category)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["message"] = f"Created ticket #{created.id}: {created.title}"
            st.rerun()
