import streamlit as st
import auth
import db
import rag
from theme import load_css, page_header, sidebar_identity
from voice_component import voice_orb

st.set_page_config(page_title="AI Assistant", page_icon="🤖", layout="wide")
db.init_db()
load_css()
auth.require_login()
user = auth.current_user()

with st.sidebar:
    sidebar_identity()
    st.divider()
    st.markdown("**💬 Chat sessions**")
    if st.button("➕ New chat", use_container_width=True):
        st.session_state["current_session_id"] = None
        st.rerun()
    st.write("")
    sessions = db.get_sessions(user["id"])
    for s in sessions:
        c1, c2 = st.columns([4, 1])
        active = st.session_state.get("current_session_id") == s["id"]
        if c1.button(("● " if active else "") + s["title"], key=f"sess_{s['id']}", use_container_width=True):
            st.session_state["current_session_id"] = s["id"]
            st.rerun()
        if c2.button("🗑️", key=f"del_{s['id']}"):
            db.delete_session(s["id"])
            if st.session_state.get("current_session_id") == s["id"]:
                st.session_state["current_session_id"] = None
            st.rerun()

page_header("🤖", "AI Assistant", "Ask anything about your training material — by text or voice.")

if "current_session_id" not in st.session_state:
    st.session_state["current_session_id"] = sessions[0]["id"] if sessions else None

sid = st.session_state["current_session_id"]
messages = db.get_messages(sid) if sid else []

if not messages:
    st.info("Start a new conversation — ask a question below, or tap the orb to speak.")

last_user_text = ""
for m in messages:
    if m["role"] == "user":
        last_user_text = m["content"]
    with st.chat_message("user" if m["role"] == "user" else "assistant"):
        st.write(m["content"])
        if m["role"] == "assistant" and m["sources"]:
            with st.expander(f"📊 Sources ({len(m['sources'])})"):
                for s in m["sources"]:
                    st.markdown(f"**{s['filename']}** · page {s['page']} · relevance `{s['score']}`")
            with st.expander("🔧 How I answered — 1 tool call(s)"):
                st.caption(f'Searched the knowledge base for: "{last_user_text}"')
                st.write(f"Ran a semantic search over the document index and retrieved "
                         f"{len(m['sources'])} matching passages from "
                         f"{len(set(s['filename'] for s in m['sources']))} document(s), "
                         f"then answered using those excerpts as context.")
        if m["role"] == "assistant" and m["followups"]:
            st.write("")
            cols = st.columns(len(m["followups"]))
            for i, fq in enumerate(m["followups"]):
                if cols[i].button(fq, key=f"followup_{m['id']}_{i}"):
                    st.session_state["pending_query"] = fq
                    st.rerun()

st.divider()

# ---------------- Voice orb ----------------
last_ai = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
speak_text = last_ai["content"] if last_ai and st.session_state.get("just_answered") else ""
speak_id = str(last_ai["id"]) if last_ai else ""
st.session_state["just_answered"] = False

result = voice_orb(speak_text=speak_text, speak_id=speak_id, listen=True, active=True,
                    lang="en-US", key="assistant_orb")

voice_query = None
if result and result.get("kind") == "transcript":
    if st.session_state.get("last_voice_nonce") != result.get("nonce"):
        st.session_state["last_voice_nonce"] = result.get("nonce")
        voice_query = result.get("text")

# ---------------- Text input ----------------
typed_query = st.chat_input("Type your question...")
pending_query = st.session_state.pop("pending_query", None)
final_query = typed_query or voice_query or pending_query

if final_query:
    if sid is None:
        sid = db.create_session(user["id"], final_query[:40])
        st.session_state["current_session_id"] = sid
    db.add_message(sid, "user", final_query)
    history = db.get_messages(sid)
    with st.spinner("Searching the knowledge base and thinking..."):
        try:
            answer, followups, sources = rag.ask_assistant(final_query, history=history, domain=user.get("domain"))
        except Exception as e:
            answer, followups, sources = f"I couldn't reach the model just now — {e}", [], []
    db.add_message(sid, "assistant", answer, sources=sources, followups=followups)
    st.session_state["just_answered"] = True
    st.rerun()
