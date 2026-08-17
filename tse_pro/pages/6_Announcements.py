import streamlit as st
import auth
import db
from theme import load_css, page_header, sidebar_identity

st.set_page_config(page_title="Announcements", page_icon="📢", layout="wide")
db.init_db()
load_css()
auth.require_login()

with st.sidebar:
    sidebar_identity()

page_header("📢", "Announcements", "Publish news, schedule changes, and updates — trainees see them on their home page.")

if auth.is_admin():
    with st.form("post_ann", clear_on_submit=True):
        title = st.text_input("Title", placeholder="New Finacle training batch starts Monday")
        message = st.text_area("Message (markdown supported)", placeholder="Details, links, and instructions...")
        category = st.selectbox("Category", ["General", "Schedule", "Exam", "System"])
        if st.form_submit_button("📢 Publish", type="primary"):
            if title.strip() and message.strip():
                db.add_announcement(title.strip(), message.strip(), category, auth.current_user()["email"])
                st.success("Published.")
            else:
                st.warning("Add a title and a message.")
    st.divider()

anns = db.get_announcements()
if not anns:
    st.info("No announcements yet.")
for a in anns:
    st.markdown(f"""
        <div class="ts-news">
          <div class="ts-news-head"><span class="ts-news-title">{a['title']}</span></div>
          <div class="ts-news-body">{a['message']}</div>
          <div class="ts-news-meta">{a['category']} · {a['created_at']}</div>
        </div>
    """, unsafe_allow_html=True)
