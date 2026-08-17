import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Learning Path Builder", page_icon="🧭", layout="wide")
db.init_db()
load_css()
auth.require_admin()

with st.sidebar:
    sidebar_identity()

page_header("🧭", "Learning Path Builder",
            "Design the curriculum. Existing weeks are frozen to prevent sync issues. Delete a week to recreate it.")

if st.button("➕ Draft Next Week", type="primary"):
    db.draft_next_week(auth.current_user()["email"])
    st.rerun()

weeks = db.get_learning_path_weeks()
if not weeks:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">🧭</div>
          <div class="ts-empty-title">No weeks yet</div>
          <div class="ts-empty-body">Click "Draft Next Week" to start building the curriculum.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

documents = db.get_documents()
doc_map = {d["filename"]: d["id"] for d in documents}
doc_by_id = {d["id"]: d for d in documents}

FORMAT_LABELS = {
    "mcq": "Choose the correct answer",
    "fillblank": "Fill in the blanks",
    "qa": "Question & answer",
}

tabs = st.tabs([f"{'✅ ' if w['published'] else ''}Week {w['week_number']}" for w in weeks])

for tab, week in zip(tabs, weeks):
    with tab:
        wid = week["id"]
        st.markdown(f"### Week {week['week_number']}")

        st.markdown("#### 📖 Reading days (1–4)")
        st.caption("One PDF per day. Trainees must finish every page of a day to unlock the next.")

        for day in range(1, 5):
            doc_id = week.get(f"day{day}_doc_id")
            c1, c2, c3, c4 = st.columns([1, 3, 3, 1])
            c1.markdown(f"**Day {day}**")
            if doc_id and doc_by_id.get(doc_id):
                d = doc_by_id[doc_id]
                c2.markdown(f"📄 **{d['filename']}** · {d['pages']} pages")
                c3.caption("Frozen — delete the week to change it.")
            else:
                uploaded = c2.file_uploader("Choose file", type=["pdf"], key=f"upload_{wid}_{day}",
                                             label_visibility="collapsed")
                existing_name = c3.selectbox("existing document", ["— existing document —"] + list(doc_map.keys()),
                                              key=f"existing_{wid}_{day}", label_visibility="collapsed")
                if c4.button("⬆️ Set", key=f"set_{wid}_{day}"):
                    if uploaded is not None:
                        file_bytes = uploaded.read()
                        pages, chunks = rag.extract_pdf_chunks(file_bytes)
                        size_kb = round(len(file_bytes) / 1024, 4)
                        new_did = db.add_document(uploaded.name, pages, size_kb, auth.current_user()["email"],
                                                   file_blob=file_bytes, topic=f"Week {week['week_number']} — Day {day}")
                        db.add_chunks(new_did, chunks)
                        rag._build_index.clear()
                        db.set_week_day_document(wid, day, new_did)
                        st.success(f"Day {day} set to {uploaded.name}.")
                        st.rerun()
                    elif existing_name != "— existing document —":
                        db.set_week_day_document(wid, day, doc_map[existing_name])
                        st.success(f"Day {day} set to {existing_name}.")
                        st.rerun()
                    else:
                        st.warning("Choose a file or pick an existing document first.")

        st.divider()
        st.markdown("#### 📝 Day 5 — exam formats & timers")
        formats = week["formats"]
        new_formats = {}
        for qtype, label in FORMAT_LABELS.items():
            cfg = formats.get(qtype, {"enabled": True, "questions": 5, "timer_min": 10})
            fc1, fc2, fc3 = st.columns([3, 2, 2])
            enabled = fc1.checkbox(label, value=cfg.get("enabled", True), key=f"en_{wid}_{qtype}")
            n_q = fc2.number_input("Questions", min_value=1, max_value=20, value=int(cfg.get("questions", 5)),
                                    key=f"nq_{wid}_{qtype}")
            timer = fc3.number_input("Timer (min)", min_value=1, max_value=120, value=int(cfg.get("timer_min", 10)),
                                      key=f"tm_{wid}_{qtype}")
            new_formats[qtype] = {"label": label, "enabled": enabled, "questions": int(n_q), "timer_min": int(timer)}

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save formats", key=f"savefmt_{wid}"):
            db.save_week_formats(wid, new_formats)
            st.success("Exam formats saved.")
            st.rerun()

        last_gen = f"Last generated {week['exam_generated_at']}" if week.get("exam_generated_at") else "Not generated yet"
        if bc2.button("✨ Generate exam with AI", key=f"genexam_{wid}"):
            day_doc_ids = [week.get(f"day{d}_doc_id") for d in range(1, 5)]
            day_doc_ids = [d for d in day_doc_ids if d]
            if not day_doc_ids:
                st.warning("Set at least one reading day's document before generating the exam.")
            else:
                context = ""
                for did in day_doc_ids:
                    chunks = db.get_chunks_for_document(did)
                    context += "\n\n".join(c_["text"] for c_ in chunks[:15]) + "\n\n"
                enabled_formats = {k: v for k, v in week["formats"].items() if v.get("enabled")}
                if not enabled_formats:
                    st.warning("Enable at least one exam format above.")
                else:
                    with st.spinner("Generating mixed exam with AI..."):
                        try:
                            questions, total_timer, total_marks = rag.generate_learning_path_exam(context, enabled_formats)
                            eid = db.save_exam(
                                f"Week {week['week_number']} — Assessment", "Auto-generated from this week's reading material.",
                                "mixed", day_doc_ids[0], questions, auth.current_user()["email"])
                            db.set_week_exam(wid, eid)
                            st.success(f"Generated {len(questions)} questions ({total_marks} marks, ~{total_timer} min).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not generate exam: {e}")
        st.caption(last_gen)

        st.divider()
        st.markdown("#### 🚀 Publish")
        if week["published"]:
            st.success(f"✅ Week {week['week_number']} is live. Trainees can see it on their Learning Path.")
            if st.button("Unpublish", key=f"unpub_{wid}"):
                db.set_week_published(wid, False)
                st.rerun()
        else:
            ready = all(week.get(f"day{d}_doc_id") for d in range(1, 5)) and week.get("exam_id")
            if not ready:
                st.info("Set all 4 reading days and generate the Day 5 exam before publishing.")
            if st.button("Publish", key=f"pub_{wid}", disabled=not ready, type="primary"):
                db.set_week_published(wid, True)
                st.rerun()

        if week.get("exam_id"):
            with st.expander("Generated exam preview"):
                exam = db.get_exam(week["exam_id"])
                if exam:
                    for i, q in enumerate(exam["questions"]):
                        st.markdown(f"**Q{i+1}. ({q.get('type')})** {q['question']}")
                        if q.get("type") == "mcq":
                            for oi, o in enumerate(q["options"]):
                                st.caption(("✅ " if oi == q["correct_index"] else "· ") + o)
                        elif q.get("type") == "truefalse":
                            st.caption(f"Answer: {q.get('correct_answer')}")
                        elif q.get("type") == "fillblank":
                            st.caption(f"Answer: {q.get('correct_answer')}")

        st.divider()
        confirm_del = st.checkbox("Confirm delete this week", key=f"confdel_{wid}")
        if st.button("🗑️ Delete week", key=f"del_{wid}", disabled=not confirm_del):
            db.delete_week(wid)
            st.rerun()
