import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, badge, sidebar_identity

st.set_page_config(page_title="Exam Management", page_icon="📝", layout="wide")
db.init_db()
load_css()
auth.require_admin()

with st.sidebar:
    sidebar_identity()

page_header("📝", "Exam Management", "Create assessments, assign them to trainees, and review AI-graded results.")

tab_create, tab_assign, tab_results = st.tabs(["Create exam", "Assign", "Results"])

# ==================== CREATE ====================
with tab_create:
    exam_type = st.radio("Exam type", ["written", "voice"], horizontal=True,
                          format_func=lambda x: "✍️ Written — typed answers, marks" if x == "written"
                          else "🎙️ Voice — spoken answers, AI-graded")

    st.markdown("**✨ Generate questions with AI (optional)**")
    documents = db.get_documents()
    doc_options = {d["filename"]: d["id"] for d in documents}
    c1, c2, c3 = st.columns([3, 1, 1])
    source_doc_name = c1.selectbox("Source document", ["(none — write manually)"] + list(doc_options.keys()))
    n_questions = c2.number_input("Questions", min_value=1, max_value=20, value=5)
    qtype = c3.selectbox("Question format", list(rag.QUESTION_TYPES.keys()),
                          format_func=lambda k: rag.QUESTION_TYPES[k][0])

    if "draft_questions" not in st.session_state:
        st.session_state.draft_questions = None

    if st.button("✨ Generate", type="primary"):
        if source_doc_name == "(none — write manually)":
            st.warning("Pick a source document to generate from, or write questions manually below.")
        else:
            did = doc_options[source_doc_name]
            chunks = db.get_chunks_for_document(did)
            context = "\n\n".join(c["text"] for c in chunks[:25])
            with st.spinner("Generating questions..."):
                try:
                    st.session_state.draft_questions = rag.generate_exam_questions(context, n_questions, qtype)
                    st.session_state.draft_qtype = qtype
                    st.session_state.draft_source_doc = did
                    st.success(f"Generated {len(st.session_state.draft_questions)} questions.")
                except Exception as e:
                    st.error(f"Could not generate questions: {e}")

    if st.session_state.draft_questions:
        with st.expander(f"Preview generated questions ({len(st.session_state.draft_questions)})", expanded=True):
            for i, q in enumerate(st.session_state.draft_questions):
                st.markdown(f"**Q{i+1}.** {q['question']}")
                if q.get("type") == "mcq":
                    for oi, o in enumerate(q["options"]):
                        st.caption(("✅ " if oi == q["correct_index"] else "· ") + o)

    st.divider()
    st.markdown("**Exam details**")
    title = st.text_input("Exam title", placeholder="e.g. Module 1 — Fundamentals Assessment")
    description = st.text_area("Description / instructions",
                                placeholder="Answer all questions in your own words. Be specific.")

    if st.button("Save exam"):
        if not title.strip():
            st.warning("Give the exam a title.")
        elif not st.session_state.draft_questions:
            st.warning("Generate questions first (manual question authoring isn't included in this build yet).")
        else:
            eid = db.save_exam(title.strip(), description.strip(),
                                st.session_state.get("draft_qtype", "mcq"),
                                st.session_state.get("draft_source_doc"),
                                st.session_state.draft_questions,
                                auth.current_user()["email"])
            st.session_state.draft_questions = None
            st.success(f"Exam \"{title}\" saved (ID {eid}). Head to the Assign tab to assign it.")

# ==================== ASSIGN ====================
with tab_assign:
    exams = db.get_exams()
    trainees = db.get_users(role="trainee")
    if not exams:
        st.info("No exams yet — create one in the Create exam tab.")
    elif not trainees:
        st.info("No trainees registered yet — create some in User Management.")
    else:
        exam_map = {f"{e['title']} (ID {e['id']})": e["id"] for e in exams}
        chosen_exam = st.selectbox("Exam", list(exam_map.keys()))
        trainee_map = {f"{t['name']} ({t['email']})": t["id"] for t in trainees}
        chosen_trainees = st.multiselect("Assign to", list(trainee_map.keys()))
        if st.button("Assign exam", type="primary"):
            if not chosen_trainees:
                st.warning("Pick at least one trainee.")
            else:
                eid = exam_map[chosen_exam]
                uids = [trainee_map[t] for t in chosen_trainees]
                db.assign_exam(eid, uids)
                st.success(f"Assigned to {len(uids)} trainee(s).")

# ==================== RESULTS ====================
with tab_results:
    exams = db.get_exams()
    if not exams:
        st.info("No exams yet.")
    else:
        exam_map = {f"{e['title']} (ID {e['id']})": e["id"] for e in exams}
        chosen = st.selectbox("Exam", list(exam_map.keys()), key="results_exam_select")
        eid = exam_map[chosen]
        assignments = db.get_assignments_for_exam(eid)
        attempts = {a["user_id"]: a for a in db.get_attempts(exam_id=eid)}
        if not assignments:
            st.info("This exam hasn't been assigned to anyone yet.")
        for a in assignments:
            u = db.get_user_by_id(a["user_id"])
            attempt = attempts.get(a["user_id"])
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{u['name']}** — {u['email']}")
            if attempt:
                pct = round(attempt['score'] / attempt['max_score'] * 100) if attempt['max_score'] else 0
                c2.markdown(f"{attempt['score']} / {attempt['max_score']} marks ({pct}%)")
                if c3.button("Improvement focus", key=f"focus_{u['id']}_{eid}"):
                    st.session_state["focus_user_id"] = u["id"]
                    st.session_state["focus_exam_id"] = eid
                    st.switch_page("pages/8_Improvement_Focus.py")
            else:
                c2.markdown(badge("Pending", "warn"), unsafe_allow_html=True)
