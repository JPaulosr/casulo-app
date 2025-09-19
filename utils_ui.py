# utils_ui.py
import streamlit as st
import base64
from pathlib import Path

def set_bg_logo(
    url: str | None = None,
    local_path: str | None = None,
    scope: str = "container",   # "container" (recomendado) ou "app"
    opacity: float = 0.06,
    size: str = "65%",
    position: str = "center",
    fixed: bool = True,
    blur_px: float = 1.5,
    overlay: str | None = "radial-gradient(circle at 50% 50%, rgba(0,0,0,.35), rgba(0,0,0,.65) 60%, rgba(0,0,0,.75) 100%)"
):
    """
    Marca d’água bonita:
      - scope="container": só no bloco central (fica mais clean)
      - overlay: gradiente que “apaga” um pouco a imagem pra não brigar com o texto
      - blur_px: 1–2px deixa suave
    """
    if not url and not local_path:
        return

    if local_path:
        p = Path(local_path)
        if not p.exists(): return
        mime = "image/png" if p.suffix.lower()==".png" else "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode()
        img_layer = f"url('data:{mime};base64,{b64}')"
    else:
        img_layer = f"url('{url}')"

    bg_layers = f"{overlay}, {img_layer}" if overlay else img_layer
    attach = "fixed" if fixed else "scroll"
    target = ".main .block-container::before" if scope=="container" else ".stApp::before"

    css = f"""
    <style>
    {target} {{
        content: "";
        position: fixed; inset: 0;
        background-image: {bg_layers};
        background-repeat: no-repeat;
        background-position: {position};
        background-size: {size};
        opacity: {opacity};
        filter: blur({blur_px}px);
        pointer-events: none;
        z-index: 0;
        background-attachment: {attach};
    }}
    .stApp > * {{ position: relative; z-index: 1; }}
    /* Mobile: reduz a marca d'água */
    @media (max-width: 700px) {{
      {target} {{
        background-size: 80%;
        opacity: {min(opacity*0.8, 0.08):.2f};
        filter: blur({max(0.0, blur_px-0.5):.1f}px);
      }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
