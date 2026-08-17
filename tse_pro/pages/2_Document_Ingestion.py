import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, metric, sidebar_identity

st.set_page_config(page_title="Document Ingestion", page_icon="📄", layout="wide")
db.init_db()
load_css()
auth.require_admin()

with st.sidebar:
    sidebar_identity()

page_header("📄", "Document Ingestion", "Upload training PDFs — they're chunked, embedded, tagged to a course/topic, and made instantly searchable.")

courses = db.get_courses()
course_map = {c["name"]: c["id"] for c in courses}

uploaded = st.file_uploader("Drop PDF files here", type=["pdf"], accept_multiple_files=True,
                             label_visibility="collapsed")

c1, c2 = st.columns(2)
course_name = c1.selectbox("Course this material belongs to", list(course_map.keys()))
topic = c2.text_input("Topic / folder", placeholder="e.g. Data Structures, Supply Chain Visibility")

if st.button("🔑 Build index", type="primary"):
    if not uploaded:
        st.warning("Upload at least one PDF first.")
    elif not topic.strip():
        st.warning("Give this material a topic so it's organized and reusable for study plans/interview prep.")
    else:
        course_id = course_map[course_name]
        progress = st.progress(0.0, text="Processing...")
        for i, f in enumerate(uploaded):
            file_bytes = f.read()
            pages, chunks = rag.extract_pdf_chunks(file_bytes)
            size_kb = round(len(file_bytes) / 1024, 4)
            did = db.add_document(f.name, pages, size_kb, auth.current_user()["email"],
                                   file_blob=file_bytes,
                                   course_id=course_id, topic=topic.strip())
            db.add_chunks(did, chunks)
            progress.progress((i + 1) / len(uploaded), text=f"Indexed {f.name} — {len(chunks)} chunks")
        rag._build_index.clear()  # bust the TF-IDF cache so new chunks are searchable immediately
        st.success(f"Indexed {len(uploaded)} document(s) under {course_name} → {topic.strip()}.")
        st.rerun()

st.divider()
st.markdown('<div class="ts-section-title" style="font-size:1.1rem;">Current index</div>', unsafe_allow_html=True)

documents = db.get_documents()
total_chunks = db.count_chunks()
c1, c2, c3 = st.columns(3)
with c1: metric("Documents", len(documents))
with c2: metric("Total chunks", total_chunks)
with c3: metric("Courses in use", len({d["course_id"] for d in documents if d.get("course_id")}))

st.write("")
if not documents:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">📄</div>
          <div class="ts-empty-title">No documents indexed yet</div>
          <div class="ts-empty-body">Upload a PDF above and tag it with a course and topic.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

view = st.radio("View", ["📁 By course / topic", "📋 Flat list"], horizontal=True, label_visibility="collapsed")

if view == "📋 Flat list":
    rows = []
    for d in documents:
        n_chunks = len(db.get_chunks_for_document(d["id"]))
        rows.append({
            "Document": d["filename"], "Course": d.get("course_name") or "—", "Topic": d.get("topic") or "—",
            "Pages": d["pages"], "Chunks": n_chunks, "Size (KB)": d["size_kb"],
            "Uploaded by": d["uploaded_by"], "Uploaded at": d["uploaded_at"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    by_course = {}
    for d in documents:
        by_course.setdefault(d.get("course_name") or "Untagged", {}).setdefault(d.get("topic") or "Untagged", []).append(d)
    for course, topics in by_course.items():
        with st.expander(f"📁 {course}  ({sum(len(v) for v in topics.values())} document(s))"):
            for topic_name, docs in topics.items():
                st.markdown(f"**📂 {topic_name}**")
                for d in docs:
                    n_chunks = len(db.get_chunks_for_document(d["id"]))
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📄 {d['filename']} — {d['pages']} pages, {n_chunks} chunks, "
                                f"uploaded {d['uploaded_at']}", unsafe_allow_html=True)
