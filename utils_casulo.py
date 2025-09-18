# utils_casulo.py
import re, unicodedata
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe
from datetime import datetime
from gspread.utils import rowcol_to_a1

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _normalize_private_key(k: str) -> str:
    return k.replace("\\n", "\n") if isinstance(k, str) else k

def _norm(s: str) -> str:
    s = (s or "").strip().casefold()
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

@st.cache_resource
def connect():
    sa = st.secrets.get("gcp_service_account", None)
    if not sa:
        st.error("gcp_service_account ausente em st.secrets")
        st.stop()
    if "private_key" in sa:
        sa["private_key"] = _normalize_private_key(sa["private_key"])
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sid = st.secrets.get("SHEET_ID", None)
    if not sid:
        st.error("SHEET_ID ausente em st.secrets")
        st.stop()
    return gc.open_by_key(sid)

def read_ws(ss, title, cols=None):
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
    # mapeia nome normalizado -> url
    if "FotoURL" not in df_pac.columns:
        return {}
    out = {}
    for _, r in df_pac.iterrows():
        nome = str(r.get("Nome","")).strip()
        url = str(r.get("FotoURL","")).strip()
        if nome and url:
            out[_norm(nome)] = url
    return out
