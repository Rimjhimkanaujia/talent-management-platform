import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="My Exams", page_icon="🧾", layout="wide")
db.init_db()
load_css()
auth.require_login()
user = auth.current_user()

with st.sidebar:
    sidebar_identity()

page_header("🧾", "My Exams", "Assessments assigned to you.")

for key, default in [("taking_exam_id", None), ("exam_answers", {}), ("last_audio_hash", {})]:
    if key not in st.session_state:
        st.session_state[key] = default

assignments = db.get_assignments_for_user(user["id"])
pending = [a for a in assignments if a["status"] == "pending"]
completed_assignments = [a for a in assignments if a["status"] == "completed"]

tab_pending, tab_completed = st.tabs([f"Pending ({len(pending)})", f"Completed ({len(completed_assignments)})"])

with tab_pending:
    if not pending:
        st.info("No pending exams — you're all caught up.")
    for a in pending:
        exam = db.get_exam(a["exam_id"])
        with st.container(border=True):
            type_label = {"written": "✍️ Written", "voice": "🎙️ Voice", "mixed": "🧩 Learning Path exam"}.get(exam["exam_type"], exam["exam_type"])
            st.markdown(f"**{exam['title']}**  ·  {type_label}")
            st.caption(exam["description"])
            st.caption(f"{len(exam['questions'])} question(s)")
            if st.button("Take exam", key=f"take_{exam['id']}"):
                st.session_state.taking_exam_id = exam["id"]
                st.session_state.exam_answers = {}
                st.rerun()

    if st.session_state.taking_exam_id:
        exam = db.get_exam(st.session_state.taking_exam_id)
        st.divider()
        st.subheader(exam["title"])

        for i, q in enumerate(exam["questions"]):
            with st.container(border=True):
                qtype = q.get("type", "short")
                timer_note = f" · ⏱️ {q['timer_min']} min" if q.get("timer_min") else ""
                st.markdown(f"**Q{i+1}.** {q['question']}{timer_note}")
                if qtype == "mcq":
                    choice = st.radio("answer", q["options"], key=f"ans_{i}", index=None, label_visibility="collapsed")
                    st.session_state.exam_answers[i] = q["options"].index(choice) if choice is not None else None
                elif qtype == "truefalse":
                    choice = st.radio("answer", ["True", "False"], key=f"ans_{i}", index=None, label_visibility="collapsed")
                    st.session_state.exam_answers[i] = (choice == "True") if choice is not None else None
                elif qtype == "fillblank":
                    ans = st.text_input("answer", key=f"ans_{i}", label_visibility="collapsed",
                                         placeholder="Fill in the blank...")
                    st.session_state.exam_answers[i] = ans
                elif qtype == "qa":
                    ans = st.text_area("answer", key=f"ans_{i}", label_visibility="collapsed",
                                        placeholder="Write your answer...")
                    st.session_state.exam_answers[i] = ans
                elif exam["exam_type"] == "voice":
                    audio = st.audio_input(f"Record your answer to Q{i+1}", key=f"audio_{i}")
                    if audio is not None:
                        h = hash(audio.getvalue())
                        if st.session_state.last_audio_hash.get(i) != h:
                            st.session_state.last_audio_hash[i] = h
                            try:
                                import speech_recognition as sr
                                r = sr.Recognizer()
                                with sr.AudioFile(audio) as source:
                                    audio_data = r.record(source)
                                text = r.recognize_google(audio_data)
                                st.session_state.exam_answers[i] = text
                            except Exception as e:
                                st.warning(f"Couldn't transcribe: {e}")
                    if st.session_state.exam_answers.get(i):
                        st.caption(f"Transcribed: \u201c{st.session_state.exam_answers[i]}\u201d")
                else:
                    ans = st.text_area("answer", key=f"ans_{i}", label_visibility="collapsed",
                                        placeholder="Write your answer...")
                    st.session_state.exam_answers[i] = ans

        if st.button("Submit for grading", type="primary"):
            questions = exam["questions"]
            answers = st.session_state.exam_answers
            with st.spinner("Grading..."):
                distinct_types = {q.get("type", "short") for q in questions}
                if exam["exam_type"] == "mixed" or len(distinct_types) > 1:
                    try:
                        feedback, score, max_score = rag.grade_mixed_exam(questions, answers)
                    except Exception as e:
                        st.error(f"Grading failed: {e}")
                        st.stop()
                elif questions and questions[0].get("type") == "mcq":
                    feedback = []
                    for i, q in enumerate(questions):
                        a = answers.get(i)
                        if a is None:
                            feedback.append({"score": 0, "feedback": "Not attempted."})
                        elif a == q["correct_index"]:
                            feedback.append({"score": 1, "feedback": "Correct."})
                        else:
                            feedback.append({"score": 0, "feedback": f"Not quite — {q.get('explanation','review this concept.')}"})
                    score = sum(f["score"] for f in feedback)
                    max_score = len(questions)
                else:
                    qtype = questions[0].get("type", "short") if questions else "short"
                    marks_per_q = rag.QUESTION_TYPES.get(qtype, ("", 5))[1]
                    try:
                        feedback = rag.grade_written_answers(questions, answers, marks_per_q)
                        score = sum(f["score"] for f in feedback)
                        max_score = len(questions) * marks_per_q
                    except Exception as e:
                        st.error(f"Grading failed: {e}")
                        st.stop()
            db.save_attempt(exam["id"], user["id"], answers, score, max_score, feedback)
            st.session_state.taking_exam_id = None
            st.session_state.exam_answers = {}
            st.success(f"Submitted! Score: {score} / {max_score}")
            st.rerun()

with tab_completed:
    attempts = db.get_attempts(user_id=user["id"])
    if not attempts:
        st.info("No completed exams yet.")
    for att in attempts:
        exam = db.get_exam(att["exam_id"])
        pct = round(att["score"] / att["max_score"] * 100) if att["max_score"] else 0
        with st.container(border=True):
            st.markdown(f"**{exam['title'] if exam else 'Deleted exam'}**")
            st.markdown(f"Score: {att['score']} / {att['max_score']} ({pct}%)")
            st.caption(f"Submitted {att['submitted_at']}")
            if exam:
                with st.expander("Detailed feedback"):
                    for i, q in enumerate(exam["questions"]):
                        st.markdown(f"**Q{i+1}.** {q['question']}")
                        st.caption(f"Your answer: {att['answers'].get(str(i), att['answers'].get(i, '(blank)'))}")
                        st.write(att["feedback"][i]["feedback"])
