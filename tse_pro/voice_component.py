"""Wraps voice_orb_static/index.html as a bidirectional Streamlit component."""
import os
import streamlit.components.v1 as components

_component_func = components.declare_component(
    "voice_orb",
    path=os.path.join(os.path.dirname(__file__), "voice_orb_static"),
)


def voice_orb(speak_text="", speak_id="", listen=True, active=True, lang="en-US", key=None):
    """Renders the voice orb. Returns {'kind':'transcript','text':...,'lang':...,'nonce':...}
    when the user finishes speaking, or None otherwise."""
    return _component_func(
        speak_text=speak_text, speak_id=speak_id, listen=listen,
        active=active, lang=lang, key=key, default=None,
    )
