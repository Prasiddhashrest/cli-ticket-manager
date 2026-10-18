"""Professional Streamlit dashboard sharing the CLI's SQLite repository.

Launch: python -m streamlit run dashboard.py
"""

import csv
from collections import Counter
from dataclasses import asdict
from io import StringIO

import streamlit as st

from ticket_manager.cli import CATEGORIES, DEFAULT_DB, PRIORITIES
from ticket_manager.models import TicketEvent
from ticket_manager.storage import TicketRepository


st.set_page_config(
    page_title="Support Desk | IT Ticket Manager", page_icon="🎫", layout="wide"
)

# Static CSS only; user-entered ticket text is rendered via Streamlit native widgets.
st.markdown(
    """
    <style>
      .block-container {max-width: 1450px; padding-top: 1.5rem; padding-bottom: 3rem;}
      div[data-testid="stMetric"] {
        background: rgba(125, 142, 169, .08);
        border: 1px solid rgba(125, 142, 169, .19);
        border-radius: 13px; padding: 16px 18px;
      }
      div[data-testid="stMetricLabel"] {font-weight: 600;}
      div[data-testid="stDataFrame"] {border-radius: 10px; overflow: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

repo = TicketRepository(DEFAULT_DB)
all_tickets = repo.list_tickets()


def show_message(text: str):
    st.session_state["message"] = text
    st.rerun()


def event_action(event: TicketEvent) -> str:
    if event.event_type == "created":
        return "Created ticket"
    if event.event_type == "assigned":
        return "Changed technician"
    if event.event_type == "status_changed":
        return "Changed status"
    return "Edited {}".format((event.field_name or "ticket").replace("_", " "))


def summary(value, *, max_length=125) -> str:
    if value is None:
        return "—"
    one_line = value.replace("\r", " ").replace("\n", " ")
    return one_line if len(one_line) <= max_length else one_line[:max_length - 1] + "…"


def event_rows(events):
    return [
        {
            "When (UTC)": ev.created_at,
            "Ticket": "#{}".format(ev.ticket_id),
            "Action": event_action(ev),
            "Previous": summary(ev.old_value),
            "New": summary(ev.new_value),
        }
        for ev in events
    ]


def ticket_rows(tickets):
    return [
        {
            "ID": ticket.id,
            "Title": ticket.title,
            "Priority": ticket.priority.title(),
            "Category": ticket.category.title(),
            "Status": ticket.status.title(),
            "Technician": ticket.assigned_to or "Unassigned",
            "Created (UTC)": ticket.created_at,
        }
        for ticket in tickets
    ]


heading, subtitle = st.columns([4, 1])
with heading:
    st.title("🎫 Support Desk")
    st.caption("IT ticket management · Python + SQLite · Local demo")
with subtitle:
    st.caption("VERSION 1.3")
    st.caption("CLI + visual dashboard")

message = st.session_state.pop("message", None)
if message:
    st.success(message)

known_agents = sorted(
    {t.assigned_to for t in all_tickets if t.assigned_to}, key=str.casefold
)
with st.sidebar:
    st.title("Support Desk")
    st.caption("Find and manage IT issues")
    st.divider()
    st.subheader("Filters")
    search = st.text_input("Search tickets", placeholder="Title or description...")
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
    st.caption("Data is stored locally in data/tickets.db. Never enter real passwords or private support information.")


def matches_filters(ticket):
    needle = search.strip().casefold()
    return (
        (not needle or needle in ticket.title.casefold() or needle in ticket.description.casefold())
        and (status_filter == "all" or ticket.status == status_filter)
        and (priority_filter == "all" or ticket.priority == priority_filter)
        and (category_filter == "all" or ticket.category == category_filter)
        and (
            agent_filter is None
            or (agent_filter == "" and ticket.assigned_to is None)
            or (
                ticket.assigned_to is not None
                and ticket.assigned_to.casefold() == str(agent_filter).casefold()
            )
        )
    )


filtered_tickets = [ticket for ticket in all_tickets if matches_filters(ticket)]
overview_tab, manage_tab, create_tab, activity_tab = st.tabs(
    ["📊 Overview", "🛠 Manage tickets", "➕ New ticket", "🕘 Activity log"]
)

with overview_tab:
    total = len(all_tickets)
    open_count = sum(t.status == "open" for t in all_tickets)
    resolved_count = total - open_count
    urgent = sum(t.status == "open" and t.priority == "high" for t in all_tickets)
    unassigned = sum(t.status == "open" and not t.assigned_to for t in all_tickets)
    for column, (label, value) in zip(
        st.columns(5),
        [
            ("All tickets", total), ("Open", open_count), ("Resolved", resolved_count),
            ("High priority · open", urgent), ("Unassigned · open", unassigned),
        ],
    ):
        column.metric(label, value)

    st.divider()
    st.subheader("Workload & trends")
    st.caption("Charts and ticket table respond to sidebar filters; the metrics above summarize all tickets.")

    if filtered_tickets:
        counts_by_day = Counter(t.created_at[:10] for t in filtered_tickets)
        days = sorted(counts_by_day)
        st.markdown("**Tickets created per day**")
        st.line_chart(
            [{"Date": day, "Created": counts_by_day[day]} for day in days],
            x="Date", y="Created",
        )

        by_cat = Counter(t.category for t in filtered_tickets)
        by_priority = Counter(t.priority for t in filtered_tickets)
        first, second = st.columns(2)
        with first:
            st.markdown("**By category**")
            st.bar_chart(
                [{"Category": name.title(), "Count": by_cat[name]} for name in CATEGORIES],
                x="Category", y="Count",
            )
        with second:
            st.markdown("**By priority**")
            st.bar_chart(
                [{"Priority": name.title(), "Count": by_priority[name]} for name in PRIORITIES],
                x="Priority", y="Count",
            )
        by_agent = Counter(t.assigned_to or "Unassigned" for t in filtered_tickets)
        st.markdown("**Technician workload**")
        st.bar_chart(
            [{"Technician": name, "Count": count} for name, count in sorted(by_agent.items())],
            x="Technician", y="Count",
        )
        st.subheader("Ticket queue ({})".format(len(filtered_tickets)))
        st.dataframe(ticket_rows(filtered_tickets), hide_index=True, use_container_width=True)
    else:
        st.info("No tickets match these filters. Change the filters or create a new ticket.")

with manage_tab:
    st.subheader("Manage tickets")
    st.caption("Select a ticket, update its fields, and review its recorded changes.")
    if not filtered_tickets:
        st.info("No tickets match your sidebar filters. Adjust them to select a ticket.")
    else:
        st.dataframe(ticket_rows(filtered_tickets), hide_index=True, use_container_width=True)
        id_to_ticket = {ticket.id: ticket for ticket in filtered_tickets}
        selected_id = st.selectbox(
            "Select a ticket",
            options=list(id_to_ticket),
            format_func=lambda ticket_id: "#{} · {}".format(ticket_id, id_to_ticket[ticket_id].title),
        )
        selected = repo.get(selected_id)
        if selected:
            st.markdown("### Ticket #{} · {}".format(selected.id, selected.title))
            c1, c2, c3 = st.columns(3)
            c1.metric("Status", selected.status.title())
            c2.metric("Priority", selected.priority.title())
            c3.metric("Technician", selected.assigned_to or "Unassigned")
            st.caption("Created (UTC): {} · Last modified (UTC): {}".format(
                selected.created_at, selected.updated_at or "not recorded before v1.3"
            ))

            with st.expander("✏️ Edit ticket details", expanded=True):
                with st.form("edit_{}".format(selected.id)):
                    edited_title = st.text_input("Title", value=selected.title, max_chars=150)
                    edited_description = st.text_area(
                        "Description", value=selected.description, height=110, max_chars=5000
                    )
                    c1, c2 = st.columns(2)
                    edited_priority = c1.selectbox(
                        "Priority", PRIORITIES, index=PRIORITIES.index(selected.priority)
                    )
                    edited_category = c2.selectbox(
                        "Category", CATEGORIES, index=CATEGORIES.index(selected.category)
                    )
                    save_details = st.form_submit_button("Save changes", type="primary")
                if save_details:
                    try:
                        repo.update_ticket(
                            selected.id, title=edited_title, description=edited_description,
                            priority=edited_priority, category=edited_category,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        show_message("Ticket #{} details saved.".format(selected.id))

            with st.expander("👤 Technician & status", expanded=True):
                with st.form("agent_{}".format(selected.id)):
                    name = st.text_input("Assigned technician", value=selected.assigned_to or "")
                    col1, col2 = st.columns(2)
                    assign = col1.form_submit_button("Save technician")
                    unassign = col2.form_submit_button("Unassign")
                if assign or unassign:
                    try:
                        if assign and not name.strip():
                            raise ValueError("Enter a technician name or click Unassign.")
                        repo.set_assignee(selected.id, name if assign else None)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        show_message("Ticket #{} technician updated.".format(selected.id))

                desired = "resolved" if selected.status == "open" else "open"
                label = "✓ Resolve ticket" if desired == "resolved" else "↻ Reopen ticket"
                if st.button(label, key="status_{}".format(selected.id)):
                    repo.set_status(selected.id, desired)
                    show_message("Ticket #{} is now {}.".format(selected.id, desired))

            st.markdown("### 🕘 Ticket history")
            history = repo.list_events(ticket_id=selected.id)
            if history:
                st.dataframe(event_rows(history), hide_index=True, use_container_width=True)
            else:
                st.info("No recorded changes for this older ticket. Activity logging starts with v1.3.")

        if filtered_tickets:
            buffer = StringIO()
            fields = tuple(asdict(filtered_tickets[0]).keys())
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            for ticket in filtered_tickets:
                row = asdict(ticket)
                for field, value in row.items():
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                        row[field] = "'" + value
                writer.writerow(row)
            st.download_button(
                "⬇️ Export filtered tickets to CSV", data=buffer.getvalue(),
                file_name="support_tickets.csv", mime="text/csv",
            )

with create_tab:
    st.subheader("Create a support ticket")
    st.caption("Use mock issues only — this is a portfolio demo.")
    with st.form("new_ticket", clear_on_submit=True):
        new_title = st.text_input(
            "Issue title *", placeholder="Example: Cannot connect to office VPN", max_chars=150
        )
        new_description = st.text_area("Description", max_chars=5000)
        c1, c2 = st.columns(2)
        new_priority = c1.selectbox("Priority", PRIORITIES, index=1)
        new_category = c2.selectbox("Category", CATEGORIES)
        new_agent = st.text_input("Technician (optional)", max_chars=80)
        create = st.form_submit_button("Create ticket", type="primary")
    if create:
        try:
            ticket = repo.add(new_title, new_description, new_priority, new_category, new_agent)
        except ValueError as error:
            st.error(str(error))
        else:
            show_message("Created ticket #{} · {}".format(ticket.id, ticket.title))

with activity_tab:
    st.subheader("Activity log")
    st.caption("Most recent logged changes across tickets. Times are in UTC.")
    st.info(
        "Activity tracking starts with v1.3. We preserve older tickets but cannot reconstruct "
        "actions performed before logging was introduced."
    )
    event_limit = st.selectbox("Show recent events", (20, 50, 100, 200), index=1)
    event_ticket = st.selectbox(
        "Filter activity by ticket",
        (None,) + tuple(ticket.id for ticket in all_tickets),
        format_func=lambda value: "All tickets" if value is None else "Ticket #{}".format(value),
    )
    entries = repo.list_events(ticket_id=event_ticket, limit=event_limit)
    if entries:
        st.dataframe(event_rows(entries), hide_index=True, use_container_width=True)
    else:
        st.info("No events match your selection yet.")
