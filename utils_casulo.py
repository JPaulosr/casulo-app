# utils_casulo.py
import re, unicodedata, json
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _normalize_private_key(k: str) -> str:
    return k.replace("\\n", "\n") if isinstance(k, str) else k

@st.cache_resource(show_spinner=False)
def connect():
    # 1) Credenciais
    sa_raw = st.secrets.get("gcp_service_account", None)
    if not sa_raw:
        st.error("`gcp_service_account` ausente em st.secrets.")
        st.stop()

    # `sa_raw` pode ser um mapping do TOML ou uma string JSON.
    if isinstance(sa_raw, str):
        try:
            sa = json.loads(sa_raw)  # caso alguém tenha colocado o JSON inteiro como string
        except Exception:
            st.error("`gcp_service_account` em formato texto inválido. Use bloco TOML ou JSON válido.")
            st.stop()
    else:
        sa = dict(sa_raw)  # ✅ faz uma cópia mutável

    # normaliza a private_key sem mutar st.secrets
    sa["private_key"] = _normalize_private_key(sa.get("private_key", ""))

    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    gc = gspread.authorize(creds)

    # 2) Sheet ID (aceita SHEET_ID ou PLANILHA_URL)
    sid = st.secrets.get("SHEET_ID", "")
    if not sid:
        url = st.secrets.get("PLANILHA_URL", "")
        if "/d/" in url:
            sid = url.split("/d/")[1].split("/")[0]

    if not sid:
        st.error("Defina `SHEET_ID` (ou `PLANILHA_URL`) nos secrets.")
        st.stop()

    # debug leve (tire depois, se quiser)
    st.caption(f"🔐 Service Account: {sa.get('client_email','?')} · Sheet: {sid}")

    return gc.open_by_key(sid)
