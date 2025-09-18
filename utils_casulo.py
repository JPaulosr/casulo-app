# utils_casulo.py
import json, unicodedata
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _normalize_private_key(k: str) -> str:
    # aceita chave com \n e transforma em quebras de linha reais
    return k.replace("\\n", "\n") if isinstance(k, str) else k

def _norm(s: str) -> str:
    s = (s or "").strip().casefold()
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

@st.cache_resource(show_spinner=False)
def connect():
    # 1) Credenciais (nunca mutar st.secrets)
    sa_raw = st.secrets.get("gcp_service_account", None)
    if not sa_raw:
        st.error("`gcp_service_account` ausente em st.secrets. Configure os secrets.")
        st.stop()

    if isinstance(sa_raw, str):
        try:
            sa = json.loads(sa_raw)
        except Exception:
            st.error("`gcp_service_account` em texto inválido. Use JSON válido ou bloco TOML.")
            st.stop()
    else:
        sa = dict(sa_raw)  # cópia mutável

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

    # Debug leve (tire depois)
    st.caption(f"🔐 SA: {sa.get('client_email','?')} · Sheet: {sid}")

    try:
        return gc.open_by_key(sid)
    except gspread.SpreadsheetNotFound:
        st.error("❌ SpreadsheetNotFound: confira o SHEET_ID e se a planilha está compartilhada com o e-mail da Service Account (Editor).")
        st.stop()

def read_ws(ss, title, cols=None):
    import gspread
    try:
        ws = ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=5000, cols=max(10, (len(cols) if cols else 10)))
        if cols:
            ws.append_row(cols)

    df = get_as_dataframe(ws, evaluate_formulas=True, header=0).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="first")]
    if cols:
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols + [c for c in df.columns if c not in cols]]
    return df, ws

def append_rows(ws, dicts, default_headers=None):
    headers = ws.row_values(1)
    if not headers:
        headers = default_headers or sorted({k for d in dicts for k in d.keys()})
        ws.append_row(headers)
    hdr_norm = [unicodedata.normalize("NFKC", h).casefold() for h in headers]
    rows = []
    for d in dicts:
        d_norm = {unicodedata.normalize("NFKC", k).casefold(): v for k, v in d.items()}
        rows.append([d_norm.get(hn, "") for hn in hdr_norm])
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

def new_id(prefix):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"

def foto_map(df_pac):
    if "FotoURL" not in df_pac.columns:
        return {}
    out = {}
    for _, r in df_pac.iterrows():
        nome = str(r.get("Nome","")).strip()
        url = str(r.get("FotoURL","")).strip()
        if nome and url:
            out[_norm(nome)] = url
    return out
