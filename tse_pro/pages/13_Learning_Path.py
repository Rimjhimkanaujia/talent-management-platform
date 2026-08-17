import base64
import streamlit as st
import auth
import db
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Learning Path", page_icon="🧭", layout="wide")
db.init_db()
load_css()
auth.require_login()
user = auth.current_user()

with st.sidebar:
    sidebar_identity()

page_header("🧭", "Learning Path", "Your weekly curriculum — finish each day's reading to unlock the next, then take the Day 5 assessment.")

weeks = db.get_published_weeks()
if not weeks:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">🧭</div>
          <div class="ts-empty-title">No published weeks yet</div>
          <div class="ts-empty-body">Your admin hasn't published a learning path week yet — check back soon.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

week_labels = [f"Week {w['week_number']}" for w in weeks]
chosen_label = st.selectbox("Week", week_labels, index=len(week_labels) - 1)
week = weeks[week_labels.index(chosen_label)]

progress = db.get_week_progress(week["id"], user["id"])
done_days = sum(1 for d in range(1, 5) if progress.get(d) == "completed")
st.progress(done_days / 4, text=f"{done_days}/4 reading days complete")

tab_labels = [f"{'✅' if progress.get(d) == 'completed' else '🔒' if d > 1 and progress.get(d - 1) != 'completed' else '📖'} Day {d}" for d in range(1, 5)]
tab_labels.append("📝 Day 5 — Assessment")
tabs = st.tabs(tab_labels)

for day in range(1, 5):
    with tabs[day - 1]:
        doc_id = week.get(f"day{day}_doc_id")
        if not doc_id:
            st.info("This day hasn't been set up yet.")
            continue
        unlocked = day == 1 or progress.get(day - 1) == "completed"
        if not unlocked:
            st.warning(f"🔒 Finish Day {day - 1} first to unlock this reading.")
            continue

        doc = db.get_document(doc_id)
        blob = db.get_document_blob(doc_id)
        st.markdown(f"**{doc['filename']}** · {doc['pages']} pages")
        if blob:
            b64 = base64.b64encode(blob).decode()
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" '
                f'style="border:1px solid #E0DFDC;border-radius:12px;"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("No stored file for this document.")

        status = progress.get(day, "pending")
        if status == "completed":
            st.success(f"✅ Day {day} complete.")
        else:
            if st.button(f"✅ Mark Day {day} as read", key=f"complete_{week['id']}_{day}"):
                db.set_day_progress(week["id"], user["id"], day, "completed")
                st.rerun()

with tabs[4]:
    if done_days < 4:
        st.info("🔒 Complete all 4 reading days to unlock this week's assessment.")
    elif not week.get("exam_id"):
        st.warning("The assessment for this week hasn't been generated yet — check back soon.")
    else:
        exam = db.get_exam(week["exam_id"])
        assignments = db.get_assignments_for_user(user["id"])
        already_assigned = any(a["exam_id"] == exam["id"] for a in assignments)
        already_completed = any(a["exam_id"] == exam["id"] and a["status"] == "completed" for a in assignments)

        st.markdown(f"**{exam['title']}**")
        st.caption(exam["description"])
        st.caption(f"{len(exam['questions'])} question(s)")

        if already_completed:
            attempts = [a for a in db.get_attempts(user_id=user["id"]) if a["exam_id"] == exam["id"]]
            if attempts:
                att = attempts[0]
                pct = round(att["score"] / att["max_score"] * 100) if att["max_score"] else 0
                st.success(f"✅ Completed — {att['score']} / {att['max_score']} ({pct}%)")
            st.page_link("pages/5_My_Exams.py", label="View in My Exams →", icon="🧾")
        else:
            if not already_assigned:
                db.assign_exam(exam["id"], [user["id"]])
            st.info("Your Day 5 assessment is ready.")
            st.page_link("pages/5_My_Exams.py", label="Take the assessment in My Exams →", icon="🧾")
