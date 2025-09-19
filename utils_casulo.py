# utils_casulo.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

def _normalize_private_key(pkey: str) -> str:
    # Conserta "\n" quando vem de secrets no Streamlit Cloud
    if isinstance(pkey, str):
        return pkey.replace("\\n", "\n")
    return pkey

@st.cache_resource(show_spinner="Conectando ao Google Sheets…")
def connect():
    # 1) Ler URL/ID
    planilha_ref = st.secrets.get("PLANILHA_URL", "").strip()
    if not planilha_ref:
        raise RuntimeError(
            "PLANILHA_URL ausente em st.secrets. "
            "Abra Settings → Secrets e defina PLANILHA_URL (URL COMPLETO ou apenas o ID)."
        )

    # 2) Ler credenciais
    sa = st.secrets.get("gcp_service_account", None)
    if not sa:
        raise RuntimeError(
            "gcp_service_account ausente em st.secrets. "
            "Inclua o bloco [gcp_service_account] com as credenciais do Service Account."
        )

    # 3) Normalizar private_key (necessário no Streamlit Cloud)
    if "private_key" in sa:
        sa = dict(sa)
        sa["private_key"] = _normalize_private_key(sa["private_key"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa, scopes=scopes)
    gc = gspread.authorize(creds)

    # 4) Abrir por URL ou por ID
    try:
        if planilha_ref.startswith("http"):
            ss = gc.open_by_url(planilha_ref)
        else:
            ss = gc.open_by_key(planilha_ref)
    except gspread.SpreadsheetNotFound:
        raise RuntimeError(
            "Não encontrei a planilha pelo URL/ID informado em PLANILHA_URL. "
            "Verifique:\n"
            " • Se o ID/URL está correto; e\n"
            " • Se o e-mail do Service Account tem acesso (compartilhe como Editor)."
        )
    return ss
