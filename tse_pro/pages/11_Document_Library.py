import base64
import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Document Library", page_icon="📚", layout="wide")
db.init_db()
load_css()
auth.require_login()

with st.sidebar:
    sidebar_identity()

page_header("📚", "Document Library", "Every document indexed into the knowledge base, with in-app preview.")

documents = db.get_documents()
if not documents:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">📁</div>
          <div class="ts-empty-title">The index is empty</div>
          <div class="ts-empty-body">Ask your administrator to ingest training documents.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = documents[0]["id"]

left, right = st.columns([1, 2.2])

with left:
    for d in documents:
        n_chunks = len(db.get_chunks_for_document(d["id"]))
        selected = st.session_state["selected_doc_id"] == d["id"]
        label = f"{'📄 ' if not selected else '📖 '}{d['filename']}\n{d['pages']} pages · {n_chunks} chunks · {d['size_kb']} KB · {d['uploaded_at'][:10]}"
        if st.button(label, key=f"doc_{d['id']}", use_container_width=True,
                     type="primary" if selected else "secondary"):
            st.session_state["selected_doc_id"] = d["id"]
            st.session_state.pop("doc_summary", None)
            st.rerun()

with right:
    doc = next((d for d in documents if d["id"] == st.session_state["selected_doc_id"]), documents[0])
    blob = db.get_document_blob(doc["id"])

    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        st.markdown(f"**{doc['filename']}**")
        st.caption(f"Uploaded by {doc['uploaded_by']} on {doc['uploaded_at'][:10]}"
                   + (f" · {doc['course_name']} → {doc['topic']}" if doc.get("course_name") else ""))
    if blob:
        with c2:
            st.download_button("⬇️ Download", data=blob, file_name=doc["filename"],
                               mime="application/pdf", use_container_width=True)
    with c3:
        fullscreen = st.toggle("🖥️ Fullscreen", key=f"fs_{doc['id']}")
    with c4:
        summarize_clicked = st.button("✨ Summarize", use_container_width=True)

    if summarize_clicked:
        chunks = db.get_chunks_for_document(doc["id"])
        with st.spinner("Summarizing..."):
            try:
                st.session_state["doc_summary"] = rag.summarize_document(doc["filename"], [c_["text"] for c_ in chunks])
            except Exception as e:
                st.error(f"Could not summarize: {e}")

    if st.session_state.get("doc_summary"):
        st.info(st.session_state["doc_summary"])

    st.write("")
    if blob:
        b64 = base64.b64encode(blob).decode()
        height = 900 if fullscreen else 480
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" '
            f'style="border:1px solid #E0DFDC;border-radius:12px;"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("No stored file for this document (it was likely uploaded before in-app preview was added) — "
                   "re-upload it in Document Ingestion to enable preview and download.")
