import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Improvement Focus", page_icon="📊", layout="wide")
db.init_db()
load_css()
auth.require_admin()

with st.sidebar:
    sidebar_identity()

page_header("📊", "Improvement Focus", "AI-generated coaching insight based on a trainee's exam performance.")

users = db.get_users(role="trainee")
if not users:
    st.info("No trainees yet.")
    st.stop()

user_map = {f"{u['name']} ({u['email']})": u for u in users}
default_uid = st.session_state.pop("focus_user_id", None)
default_label = next((k for k, v in user_map.items() if v["id"] == default_uid), list(user_map.keys())[0])
chosen_label = st.selectbox("Trainee", list(user_map.keys()), index=list(user_map.keys()).index(default_label))
chosen_user = user_map[chosen_label]

attempts = db.get_attempts(user_id=chosen_user["id"])
if not attempts:
    st.info(f"{chosen_user['name']} hasn't completed any exams yet.")
    st.stop()

default_eid = st.session_state.pop("focus_exam_id", None)
attempt_map = {}
for att in attempts:
    exam = db.get_exam(att["exam_id"])
    if exam:
        attempt_map[f"{exam['title']} — {att['score']}/{att['max_score']}"] = att
default_key = next((k for k, v in attempt_map.items() if v["exam_id"] == default_eid), list(attempt_map.keys())[0])
chosen_attempt_label = st.selectbox("Exam attempt", list(attempt_map.keys()),
                                     index=list(attempt_map.keys()).index(default_key))
attempt = attempt_map[chosen_attempt_label]
exam = db.get_exam(attempt["exam_id"])

if st.button("🧠 Generate improvement focus", type="primary"):
    context = ""
    if exam.get("source_document_id"):
        chunks = db.get_chunks_for_document(exam["source_document_id"])
        context = "\n\n".join(c["text"] for c in chunks[:15])
    with st.spinner("Analyzing..."):
        try:
            analysis = rag.gap_analysis(
                chosen_user["name"], exam["title"], exam["questions"], attempt["answers"],
                attempt["feedback"], attempt["score"], attempt["max_score"], context
            )
            st.session_state["last_analysis"] = analysis
        except Exception as e:
            st.error(f"Could not generate analysis: {e}")

analysis = st.session_state.get("last_analysis")
if analysis:
    pct = round(attempt["score"] / attempt["max_score"] * 100) if attempt["max_score"] else 0
    topics_html = "<br>".join(f"• {t}" for t in analysis.get("key_topics", []))
    gaps_html = "<br>".join(f"• {g}" for g in analysis.get("likely_gaps", []))
    st.markdown(f"""
        <div class="ts-card">
          <div class="ts-card-title">🤖 Improvement focus for {chosen_user['name']}</div>
          <table style="width:100%;border-collapse:collapse;margin-top:0.75rem;">
            <thead>
              <tr style="background:#0A66C2;color:white;text-align:left;">
                <th style="padding:10px;">Exam</th><th style="padding:10px;">Score</th>
                <th style="padding:10px;">Key topics covered</th><th style="padding:10px;">Likely gaps</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom:1px solid #eee;vertical-align:top;">
                <td style="padding:10px;font-weight:600;">{exam['title']}</td>
                <td style="padding:10px;">{attempt['score']} / {attempt['max_score']} ({pct}%)</td>
                <td style="padding:10px;">{topics_html}</td>
                <td style="padding:10px;">{gaps_html}</td>
              </tr>
            </tbody>
          </table>
          <div style="margin-top:1rem;"><b>Why these areas?</b><br>{analysis.get('why','')}</div>
          <div style="margin-top:0.75rem;"><b>Next steps</b><br>{analysis.get('next_steps','')}</div>
        </div>
    """, unsafe_allow_html=True)
