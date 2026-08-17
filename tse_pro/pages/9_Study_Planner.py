import streamlit as st
import auth
import db
import rag
import config
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Study Planner", page_icon="🗓️", layout="wide")
db.init_db()
load_css()
auth.require_login()
user = auth.current_user()

with st.sidebar:
    sidebar_identity()

page_header("🗓️", "Study Planner", "Turn a course and its documents into a week-by-week (or month-by-month) study timetable.")

courses = db.get_courses()
course_map = {c["name"]: c["id"] for c in courses}

with st.container(border=True):
    course_name = st.selectbox("Course", list(course_map.keys()))
    course_id = course_map[course_name]

    available_topics = db.get_topics_for_course(course_id)
    chosen_topics = st.multiselect(
        "Topics from your Document Library for this course",
        available_topics,
        default=available_topics,
        help="Tagged when documents are uploaded in Document Ingestion."
    )
    extra_topics = st.text_area("Additional topics (comma-separated, optional)",
                                 placeholder="e.g. System design basics, Behavioral interview prep")

    c1, c2, c3 = st.columns(3)
    unit = c1.radio("Plan length", ["Weeks", "Months"], horizontal=True)
    length = c2.number_input(f"Number of {unit.lower()}", min_value=1, max_value=52 if unit == "Weeks" else 12, value=4)
    duration_weeks = int(length) if unit == "Weeks" else int(length) * 4

    default_lt_index = config.LEARNER_TYPES.index(user["learner_type"]) if user.get("learner_type") in config.LEARNER_TYPES else 0
    learner_type = c3.selectbox("Learning style", config.LEARNER_TYPES, index=default_lt_index)

    if st.button("🧠 Generate study plan", type="primary"):
        all_topics = chosen_topics + [t.strip() for t in extra_topics.split(",") if t.strip()]
        with st.spinner("Building your timetable..."):
            try:
                weeks = rag.generate_study_plan(course_name, all_topics, duration_weeks, learner_type)
                title = f"{course_name} — {duration_weeks}-week plan"
                pid = db.save_study_plan(user["id"], course_id, title, duration_weeks, {"weeks": weeks})
                st.success(f"Created \"{title}\".")
                st.session_state["expand_plan_id"] = pid
                st.rerun()
            except Exception as e:
                st.error(f"Could not generate a plan: {e}")

st.divider()
st.markdown('<div class="ts-section-title" style="font-size:1.1rem;margin-bottom:0.6rem;">Your study plans</div>', unsafe_allow_html=True)

plans = db.get_study_plans(user["id"])
if not plans:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">🗓️</div>
          <div class="ts-empty-title">No study plans yet</div>
          <div class="ts-empty-body">Pick a course above and generate your first timetable.</div>
        </div>
    """, unsafe_allow_html=True)

for plan in plans:
    total_topics = sum(len(w["topics"]) for w in plan["plan"]["weeks"])
    done = sum(1 for t, s in plan["progress"].items() if s == "completed")
    expanded = st.session_state.pop("expand_plan_id", None) == plan["id"]
    with st.expander(f"{plan['title']} — {done}/{total_topics} topics completed", expanded=expanded):
        pct = round(done / total_topics * 100) if total_topics else 0
        st.progress(pct / 100, text=f"{pct}% complete")
        for w in plan["plan"]["weeks"]:
            week_label = w.get("label") or f"Week {w['week']}"
            st.markdown(f"**{week_label}**")
            for topic in w["topics"]:
                status = plan["progress"].get(topic, "pending")
                c1, c2 = st.columns([5, 2])
                checked = c1.checkbox(topic, value=(status == "completed"), key=f"chk_{plan['id']}_{topic}")
                if checked and status != "completed":
                    db.set_topic_progress(plan["id"], topic, "completed")
                    st.rerun()
                elif not checked and status == "completed":
                    db.set_topic_progress(plan["id"], topic, "pending")
                    st.rerun()
                if checked:
                    if c2.button("🎤 Interview + mock test", key=f"prep_{plan['id']}_{topic}"):
                        st.session_state["interview_topic"] = topic
                        st.session_state["interview_course"] = course_name
                        st.switch_page("pages/10_Interview_Prep.py")
        if st.button("Delete plan", key=f"del_plan_{plan['id']}"):
            db.delete_study_plan(plan["id"])
            st.rerun()
