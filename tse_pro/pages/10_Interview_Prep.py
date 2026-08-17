import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity
from voice_component import voice_orb

st.set_page_config(page_title="Interview Prep", page_icon="🎤", layout="wide")
db.init_db()
load_css()
auth.require_login()
user = auth.current_user()

with st.sidebar:
    sidebar_identity()

page_header("🎤", "Interview AI Assistant", "Live, voice-based mock interviews — the AI interviewer asks each question out loud, listens to your spoken answer, and gives feedback in real time.")

incoming_topic = st.session_state.pop("interview_topic", None)
incoming_course = st.session_state.pop("interview_course", None)

with st.container(border=True):
    topic = st.text_input("Topic", value=incoming_topic or "", placeholder="e.g. Linked Lists, EPCIS, Behavioral")
    if incoming_course:
        st.caption(f"From your study plan: {incoming_course}")
    c1, c2 = st.columns(2)
    n_questions = c1.number_input("Number of questions", min_value=3, max_value=15, value=8)

    if c2.button("✨ Generate interview questions", type="primary"):
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            # ground the questions in indexed material for this topic if any exists
            context = ""
            for d in db.get_documents():
                if (d.get("topic") or "").lower() == topic.strip().lower():
                    chunks = db.get_chunks_for_document(d["id"])
                    context += "\n\n".join(c_["text"] for c_ in chunks[:10])
                    break
            with st.spinner("Writing questions..."):
                try:
                    questions = rag.generate_interview_questions(topic.strip(), context, count=int(n_questions))
                    sid = db.save_interview_set(user["id"], topic.strip(), questions)
                    st.session_state["active_interview_id"] = sid
                    st.session_state["active_q_index"] = 0
                    st.success(f"Generated {len(questions)} questions.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not generate questions: {e}")

    if st.button("🧪 Start a mock test on this topic instead"):
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            with st.spinner("Building your mock test..."):
                try:
                    questions = rag.generate_exam_questions(topic.strip(), 5, "mcq")
                    eid = db.save_exam(f"Mock test — {topic.strip()}", "Auto-generated mock test.",
                                        "mcq", None, questions, user["email"])
                    db.assign_exam(eid, [user["id"]])
                    st.success("Mock test created and assigned to you — take it in My Exams.")
                    st.page_link("pages/5_My_Exams.py", label="Go to My Exams →", icon="🧾")
                except Exception as e:
                    st.error(f"Could not create the mock test: {e}")

st.divider()

sets = db.get_interview_sets(user["id"])
if not sets:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">🎤</div>
          <div class="ts-empty-title">No interview sets yet</div>
          <div class="ts-empty-body">Enter a topic above and generate your first mock interview.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

set_map = {f"{s['topic']} ({len(s['questions'])} q, {s['created_at']})": s["id"] for s in sets}
default_id = st.session_state.get("active_interview_id", sets[0]["id"])
default_label = next((k for k, v in set_map.items() if v == default_id), list(set_map.keys())[0])
chosen_label = st.selectbox("Interview set", list(set_map.keys()), index=list(set_map.keys()).index(default_label))
iset = db.get_interview_set(set_map[chosen_label])

if "active_q_index" not in st.session_state:
    st.session_state["active_q_index"] = 0
if "interview_scores" not in st.session_state:
    st.session_state["interview_scores"] = {}
idx = min(st.session_state["active_q_index"], len(iset["questions"]) - 1)
q = iset["questions"][idx]

live_mode = st.toggle("🔴 Live Interview Mode — AI asks, listens, grades, and auto-advances",
                       value=st.session_state.get("live_mode", True), key="live_mode")

scores = st.session_state["interview_scores"].setdefault(iset["id"], {})
if scores:
    answered = len(scores)
    avg = round(sum(scores.values()) / answered, 1)
    st.progress(min(answered / len(iset["questions"]), 1.0),
                text=f"{answered}/{len(iset['questions'])} answered · running avg {avg}/10")

st.markdown(f"**Question {idx + 1} of {len(iset['questions'])}** · difficulty: `{q.get('difficulty', 'medium')}`")

left, right = st.columns([2, 1])
with left:
    st.markdown(f"### {q['question']}")

    answer_key = f"answer_{iset['id']}_{idx}"
    typed_answer = st.text_area("Your answer (typed)", key=answer_key, placeholder="Type your answer, or use the voice orb to speak it →")

    with st.expander("Show model answer"):
        st.write(q.get("model_answer", ""))

    last_feedback = st.session_state.get(f"feedback_{iset['id']}_{idx}")
    if last_feedback:
        st.info(f"**Score: {last_feedback['score']}/10** — {last_feedback['feedback']}")

    if st.button("🧠 Get feedback on my answer"):
        candidate_answer = st.session_state.get(f"voice_answer_{iset['id']}_{idx}") or typed_answer
        if not candidate_answer:
            st.warning("Answer the question (typed or spoken) first.")
        else:
            with st.spinner("Evaluating..."):
                try:
                    result = rag.grade_interview_answer(q["question"], q.get("model_answer", ""), candidate_answer)
                    st.session_state[f"feedback_{iset['id']}_{idx}"] = result
                    scores[idx] = result["score"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not grade this answer: {e}")

    nav1, nav2, nav3 = st.columns(3)
    if nav1.button("← Previous", disabled=idx == 0):
        st.session_state["active_q_index"] = idx - 1
        st.rerun()
    if nav3.button("Next →", disabled=idx >= len(iset["questions"]) - 1):
        st.session_state["active_q_index"] = idx + 1
        st.rerun()

    if idx == len(iset["questions"]) - 1 and len(scores) == len(iset["questions"]):
        avg = round(sum(scores.values()) / len(scores), 1)
        st.divider()
        st.markdown("### 🏁 Interview complete")
        st.success(f"Overall score: **{avg}/10** across {len(scores)} questions.")

with right:
    st.markdown("**🎙️ AI Interviewer — live voice**")
    st.caption("Asks the current question aloud, listens for your spoken answer"
               + (", grades it automatically, and moves to the next question." if live_mode
                  else " — click 'Get feedback' when you're ready."))
    speak_id = f"{iset['id']}_{idx}"
    result = voice_orb(speak_text=q["question"], speak_id=speak_id, listen=True, active=True,
                        lang="en-US", key=f"orb_{speak_id}")
    if result and result.get("kind") == "transcript":
        nonce_key = f"last_nonce_{speak_id}"
        if st.session_state.get(nonce_key) != result.get("nonce"):
            st.session_state[nonce_key] = result.get("nonce")
            spoken_text = result.get("text")
            st.session_state[f"voice_answer_{iset['id']}_{idx}"] = spoken_text
            if live_mode and spoken_text:
                with st.spinner("AI interviewer is grading your answer..."):
                    try:
                        graded = rag.grade_interview_answer(q["question"], q.get("model_answer", ""), spoken_text)
                        st.session_state[f"feedback_{iset['id']}_{idx}"] = graded
                        scores[idx] = graded["score"]
                        if idx < len(iset["questions"]) - 1:
                            st.session_state["active_q_index"] = idx + 1
                    except Exception:
                        pass
            st.rerun()
    spoken = st.session_state.get(f"voice_answer_{iset['id']}_{idx}")
    if spoken:
        st.success(f"Heard: \u201c{spoken}\u201d")
