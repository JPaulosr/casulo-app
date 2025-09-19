# utils_ui.py
import streamlit as st
import base64
from pathlib import Path

def set_bg_logo(url: str | None = None,
                local_path: str | None = None,
                opacity: float = 0.06,
                size: str = "60%",
                position: str = "center",
                fixed: bool = True):
    if not url and not local_path:
        return

    if local_path:
        p = Path(local_path)
        if not p.exists():
            return
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode()
        bg = f"url('data:{mime};base64,{b64}')"
    else:
        bg = f"url('{url}')"

    attach = "fixed" if fixed else "scroll"

    css = f"""
    <style>
    .stApp::before {{
        content: "";
        position: fixed;
        inset: 0;
        background-image: {bg};
        background-repeat: no-repeat;
        background-position: {position};
        background-size: {size};
        opacity: {opacity};
        pointer-events: none;
        z-index: 0;
        background-attachment: {attach};
    }}
    .stApp > * {{ position: relative; z-index: 1; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
