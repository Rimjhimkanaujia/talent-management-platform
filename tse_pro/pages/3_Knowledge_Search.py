import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Knowledge Search", page_icon="🔍", layout="wide")
db.init_db()
load_css()
auth.require_login()

with st.sidebar:
    sidebar_identity()

page_header("🔍", "Knowledge Search", "Direct semantic search over the document index — see exactly what the AI retrieves.")

if db.count_chunks() == 0:
    st.markdown("""
        <div class="ts-empty">
          <div class="ts-empty-icon">📁</div>
          <div class="ts-empty-title">The index is empty</div>
          <div class="ts-empty-body">Ask your administrator to ingest training documents.</div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

query = st.text_input("Search query", placeholder="e.g. What is the onboarding process?")
top_k = st.slider("Results to return (Top-K)", min_value=1, max_value=15, value=5)

if st.button("🔍 Search", type="primary"):
    if not query.strip():
        st.warning("Type a search query first.")
    else:
        results = rag.search(query, top_k=top_k)
        if not results:
            st.info("No matching passages found.")
        for i, r in enumerate(results, start=1):
            st.markdown(f"""
                <div class="ts-card">
                  <div class="ts-card-title">#{i} · {r['filename']} · page {r['page']}
                    <span class="ts-badge ts-badge-outline">relevance {r['score']}</span>
                  </div>
                  <div class="ts-card-body">{r['text']}</div>
                </div>
            """, unsafe_allow_html=True)
