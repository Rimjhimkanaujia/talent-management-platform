import streamlit as st
import auth
import config
import db
import validators
from theme import load_css, hero, metric, sidebar_identity, app_footer
from logger import get_logger

log = get_logger(__name__)

st.set_page_config(page_title=config.APP_NAME, page_icon="🚀", layout="wide")
db.init_db()
load_css()

# seed a default admin on first run so there's always a way in
if not db.get_users():
    h, s = auth.hash_password(config.SEED_ADMIN_PASSWORD)
    db.create_user("EMP-0001", "Admin", config.SEED_ADMIN_EMAIL, h, s, "admin", "general")
    log.info("Seeded default admin account %s", config.SEED_ADMIN_EMAIL)

# ---------------- Not logged in: show login ----------------
if not auth.is_logged_in():
    left, mid, right = st.columns([1, 1.3, 1])
    with mid:
        st.markdown(f"""
            <div style="text-align:center;margin-top:3rem;margin-bottom:1.5rem;">
              <div style="font-size:2rem;">🚀</div>
              <div style="font-weight:800;font-size:1.6rem;">Talent <span style="color:#0A66C2;">Management Platform</span></div>
              <div style="color:#666;font-size:0.85rem;margin-top:2px;">for Employee Performance and Career Growth</div>
              <div style="color:#666;font-size:0.95rem;margin-top:6px;">Sign in to your training workspace</div>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@company.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submitted:
                if not validators.is_valid_email(email):
                    st.error("Enter a valid email address.")
                else:
                    with st.spinner("Signing in..."):
                        user, err = auth.login(email, password)
                    if err:
                        st.error(err)
                    else:
                        st.toast(f"Welcome back, {user['name'].split()[0]}!", icon="👋")
                        st.rerun()
        st.caption(f"First time here? Default admin login: **{config.SEED_ADMIN_EMAIL}** / "
                   f"**{config.SEED_ADMIN_PASSWORD}** — sign in and create real accounts from User Management.")
    app_footer()
    st.stop()

# ---------------- Logged in: dashboard ----------------
user = auth.current_user()

with st.sidebar:
    sidebar_identity()
    st.divider()
    if auth.is_admin():
        st.markdown("**Anthropic API key**")
        api_key = st.text_input("Anthropic API key", type="password",
                                 value=st.session_state.get("api_key", config.ANTHROPIC_API_KEY),
                                 placeholder="sk-ant-...", label_visibility="collapsed")
        st.session_state["api_key"] = api_key
        if api_key:
            st.caption("✅ Key set for this session.")
        else:
            st.caption("⚠️ Not set — AI features will be unavailable until you add one, "
                       "or set ANTHROPIC_API_KEY in the environment.")
        st.divider()
    if st.button("Log out", use_container_width=True):
        auth.logout()
        st.rerun()
    st.caption(f"{config.APP_NAME} {config.APP_EDITION} · v{config.APP_VERSION}")

if auth.is_admin():
    hero("Admin Control Center", "Platform health, engagement, and assessment performance in one place.")
else:
    hero(f"Welcome back, {user['name'].split()[0]} 👋",
         "Your AI-powered training workspace — ask questions, study documents, take assessments.")

announcements = db.get_announcements()
exams = db.get_exams()
documents = db.get_documents()

if auth.is_admin():
    users = db.get_users()
    trainees = db.get_users(role="trainee")
    active = db.count_active_users()
    all_attempts = db.get_attempts()
    overall_avg = round(sum(a["score"] / a["max_score"] * 100 for a in all_attempts if a["max_score"]) / len(all_attempts)) if all_attempts else 0

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1: metric("Trainees", len(trainees))
    with r1c2: metric("Active now", active)
    with r1c3: metric("Documents", len(documents))
    with r1c4: metric("Knowledge chunks", db.count_chunks())
    st.write("")
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1: metric("Chat sessions", db.count_sessions())
    with r2c2: metric("Messages", db.count_messages())
    with r2c3: metric("Exams", len(exams))
    with r2c4: metric("Avg exam score", f"{overall_avg}%")

    st.write("")
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown('<div class="ts-section-title" style="font-size:1rem;">💬 Assistant activity (30 days)</div>', unsafe_allow_html=True)
        import pandas as pd
        activity = db.messages_per_day(30)
        df_activity = pd.DataFrame(activity, columns=["date", "messages"]).set_index("date")
        st.line_chart(df_activity, height=240)
    with chart_right:
        st.markdown('<div class="ts-section-title" style="font-size:1rem;">🎯 Exam score distribution</div>', unsafe_allow_html=True)
        dist = db.score_distribution()
        df_dist = pd.DataFrame(dist, columns=["bucket", "count"]).set_index("bucket")
        st.bar_chart(df_dist, height=240)

    st.write("")
    st.markdown('<div class="ts-section-title" style="font-size:1rem;">👥 Learners</div>', unsafe_allow_html=True)
    learners = db.learners_summary()
    if learners:
        rows = [{"Name": l["name"], "Status": l["status"], "Done": l["done"],
                 "Pending": l["pending"], "Avg": f"{l['avg']}%"} for l in learners]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No trainees yet — add some in User Management.")
else:
    assignments = db.get_assignments_for_user(user["id"])
    pending = [a for a in assignments if a["status"] == "pending"]
    attempts = db.get_attempts(user_id=user["id"])
    avg = round(sum(a["score"] / a["max_score"] * 100 for a in attempts if a["max_score"]) / len(attempts)) if attempts else 0
    sessions = db.get_sessions(user["id"])
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric("Pending exams", len(pending))
    with c2: metric("Avg exam score", f"{avg}%")
    with c3: metric("Chat sessions", len(sessions))
    with c4: metric("Documents available", len(documents))

st.write("")
st.markdown('<div class="ts-section-title" style="font-size:1.1rem;margin-bottom:0.6rem;">Announcements</div>', unsafe_allow_html=True)
if announcements:
    for a in announcements[:5]:
        st.markdown(f"""
            <div class="ts-news">
              <div class="ts-news-head"><span class="ts-news-title">{a['title']}</span></div>
              <div class="ts-news-body">{a['message']}</div>
              <div class="ts-news-meta">{a['category']} · {a['created_at']}</div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">📢</div>
          <div class="ts-empty-title">No announcements yet</div>
          <div class="ts-empty-body">Admins can post updates from the Announcements page.</div>
        </div>
    """, unsafe_allow_html=True)

st.divider()
st.markdown('<div class="ts-section-title" style="font-size:1.1rem;margin-bottom:0.6rem;">Quick links</div>', unsafe_allow_html=True)
q1, q2, q3, q4 = st.columns(4)
with q1:
    st.page_link("pages/1_AI_Assistant.py", label="Ask the AI Assistant", icon="🤖")
with q2:
    st.page_link("pages/5_My_Exams.py" if not auth.is_admin() else "pages/4_Exam_Management.py",
                 label="My exams" if not auth.is_admin() else "Manage exams",
                 icon="🧾" if not auth.is_admin() else "📝")
with q3:
    st.page_link("pages/3_Knowledge_Search.py", label="Search the knowledge base", icon="🔍")
with q4:
    st.page_link("pages/9_Study_Planner.py", label="Study Planner", icon="🗓️")

q5, q6, q7, q8 = st.columns(4)
with q5:
    st.page_link("pages/13_Learning_Path.py" if not auth.is_admin() else "pages/12_Learning_Path_Builder.py",
                 label="Learning Path" if not auth.is_admin() else "Learning Path Builder", icon="🧭")
with q6:
    st.page_link("pages/10_Interview_Prep.py", label="Interview Prep (voice AI)", icon="🎤")
with q7:
    st.page_link("pages/11_Document_Library.py", label="Document Library", icon="📚")
with q8:
    if auth.is_admin():
        st.page_link("pages/7_User_Management.py", label="User Management", icon="👥")
    else:
        st.page_link("pages/6_Announcements.py", label="Announcements", icon="📢")

app_footer()
