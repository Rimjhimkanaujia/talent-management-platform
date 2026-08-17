import streamlit as st
import auth
import db
import config
import validators
import email_utils
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="User Management", page_icon="👥", layout="wide")
db.init_db()
load_css()
auth.require_admin()

with st.sidebar:
    sidebar_identity()

page_header("👥", "User Management", "Provision trainee accounts — credentials are stored hashed in SQLite, never in plain text.")

tab_create, tab_manage = st.tabs(["Create user", "Manage users"])

DOMAINS = ["general", "banking", "supply-chain", "cloud", "ai-ops", "compliance", "fullstack"]

# ==================== CREATE ====================
with tab_create:
    c1, c2 = st.columns(2)
    employee_id = c1.text_input("Employee ID", placeholder="EMP-1024")
    name = c1.text_input("Full name", placeholder="Priya Sharma")
    email = c2.text_input("Email (login credentials are sent here)", placeholder="priya@company.com")
    domain = c2.selectbox("Training domain", DOMAINS)
    role = c1.selectbox("Role", ["trainee", "admin"])
    learner_type = c2.selectbox("Learning style", ["(not set)"] + config.LEARNER_TYPES)

    st.markdown("**Password** (leave blank to auto-generate a strong one)")
    mode = st.radio("mode", ["Auto-generate", "Set manually"], horizontal=True, label_visibility="collapsed")
    manual_pw = ""
    if mode == "Set manually":
        manual_pw = st.text_input("Manual password (min 8 chars)", type="password", placeholder="Leave blank if auto")

    if st.button("➕ Create user", type="primary"):
        errors = validators.validate_new_user(employee_id, name, email, db.get_user_by_email)
        if mode == "Set manually":
            errors += validators.password_strength_errors(manual_pw)

        if errors:
            for e in errors:
                st.error(e)
        else:
            password = manual_pw if mode == "Set manually" else auth.generate_password()
            h, salt = auth.hash_password(password)
            lt = None if learner_type == "(not set)" else learner_type
            db.create_user(employee_id.strip(), name.strip(), email.strip().lower(), h, salt, role, domain, lt)
            st.toast(f"User {name} created", icon="✅")
            st.success(f"User **{name}** created.")

            sent, err = email_utils.send_registration_email(name.strip(), email.strip().lower(), password)
            if sent:
                st.success(f"📧 Registration email with the login ID and password was sent to **{email.strip()}**.")
            else:
                st.warning(err)
                st.info(f"Generated password: `{password}` — share this securely; it won't be shown again.")

    st.divider()
    st.markdown(
        f"""**Quick tips**
- The user's email is only ever taken from this form — nothing is hardcoded.
- With SMTP configured (`.env`), credentials are emailed automatically from `{config.SMTP_FROM or '(not set)'}`; otherwise the password is shown once on screen.
- Reset issues a fresh password (emailed the same way); delete removes the user and all their data.
- New users get notified automatically when you assign exams, publish learning-path weeks, or post announcements.
"""
    )

# ==================== MANAGE ====================
with tab_manage:
    users = db.get_users()
    active = db.count_active_users()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class="ts-metric"><div class="ts-metric-value">{len(users)}</div>
                        <div class="ts-metric-label">Total users</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="ts-metric"><div class="ts-metric-value">{active}</div>
                        <div class="ts-metric-label">Currently active</div></div>""", unsafe_allow_html=True)

    st.write("")
    if users:
        rows = [{
            "Employee ID": u["employee_id"], "Name": u["name"], "Email": u["email"],
            "Role": u["role"], "Domain": u["domain"], "Learning style": (u.get("learner_type") or "—").split(" — ")[0],
            "Status": u["status"], "Created": u["created_at"], "Last login": u["last_login"] or "—",
        } for u in users]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Account actions**")
        user_map = {f"{u['name']} ({u['email']})": u for u in users}
        chosen_label = st.selectbox("Select a user", list(user_map.keys()))
        chosen = user_map[chosen_label]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔑 Reset password"):
                new_pw = auth.generate_password()
                h, salt = auth.hash_password(new_pw)
                db.set_password(chosen["id"], h, salt)
                sent, err = email_utils.send_password_reset_email(chosen["name"], chosen["email"], new_pw)
                if sent:
                    st.success(f"📧 New password emailed to {chosen['email']}.")
                else:
                    st.warning(err)
                    st.info(f"New password for {chosen['name']}: `{new_pw}`")
        with c2:
            confirm = st.checkbox("Confirm deletion")
            if st.button("🗑️ Delete user", disabled=not confirm):
                if chosen["id"] == auth.current_user()["id"]:
                    st.error("You can't delete your own account while logged in.")
                else:
                    db.delete_user(chosen["id"])
                    st.success(f"Deleted {chosen['name']}.")
                    st.rerun()
    else:
        st.info("No users yet — create one in the Create user tab.")
