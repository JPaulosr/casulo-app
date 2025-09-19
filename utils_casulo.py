# utils_casulo.py — Núcleo compatível p/ todas as páginas

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import time

# -------- helpers internos --------
def _normalize_private_key(pkey: str) -> str:
    if isinstance(pkey, str):
        return pkey.replace("\\n", "\n")
    return pkey

def _get_ss():
    planilha_ref = (st.secrets.get("PLANILHA_URL", "") or "").strip()
    if not planilha_ref:
        raise RuntimeError("PLANILHA_URL ausente em st.secrets.")
    sa = st.secrets.get("gcp_service_account")
    if not sa:
        raise RuntimeError("[gcp_service_account] ausente em st.secrets.")
    sa = dict(sa)
    if "private_key" in sa:
        sa["private_key"] = _normalize_private_key(sa["private_key"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa, scopes=scopes)
    gc = gspread.authorize(creds)
    if planilha_ref.startswith("http"):
        return gc.open_by_url(planilha_ref)
    return gc.open_by_key(planilha_ref)

# -------- API estável (sempre existirá) --------
@st.cache_resource(show_spinner="Conectando ao Google Sheets…")
def connect():
    """Retorna o Spreadsheet (gspread.Spreadsheet)."""
    return _get_ss()

def read_ws(ss, title: str, expected_cols=None):
    """
    Lê (ou cria) a worksheet:
    -> retorna (df: DataFrame[str], ws: gspread.Worksheet)
    """
    import gspread
    try:
        ws = ss.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        cols = max(len(expected_cols or []), 1)
        ws = ss.add_worksheet(title=title, rows=1, cols=cols)
        if expected_cols:
            set_with_dataframe(ws, pd.DataFrame(columns=expected_cols), include_index=False)
    df = get_as_dataframe(ws, evaluate_formulas=False, dtype=str)
    if expected_cols:
        df = df.reindex(columns=expected_cols)
    return df, ws

def append_rows(ws, rows, default_headers=None):
    """
    Append seguro: aceita lista de dicts OU lista de listas.
    Se a planilha estiver vazia e houver default_headers, escreve o header.
    """
    df_atual = get_as_dataframe(ws, evaluate_formulas=False, dtype=str)
    if (df_atual is None) or df_atual.empty:
        if default_headers:
            set_with_dataframe(ws, pd.DataFrame(columns=default_headers), include_index=False)
            df_atual = pd.DataFrame(columns=default_headers)
        else:
            df_atual = pd.DataFrame()

    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        # normaliza dicts para mesmo conjunto de colunas
        cols = list(df_atual.columns) if len(df_atual.columns) else (default_headers or sorted({k for r in rows for k in r.keys()}))
        novos = pd.DataFrame(rows)
        for c in cols:
            if c not in novos.columns:
                novos[c] = ""
        novos = novos[cols]
    else:
        # assume listas alinhadas às colunas existentes ou default_headers
        cols = list(df_atual.columns) if len(df_atual.columns) else (default_headers or [])
        novos = pd.DataFrame(rows, columns=cols if cols else None)

    df_out = pd.concat([df_atual, novos], ignore_index=True)
    set_with_dataframe(ws, df_out, include_index=False)
    return True

def new_id(prefix: str = "R") -> str:
    """ID curto com prefixo + timestamp (ms)."""
    return f"{prefix}-{int(time.time()*1000)}"

def default_profissional() -> str:
    """Nome padrão do profissional (para páginas que usam)."""
    return st.secrets.get("DEFAULT_PROFISSIONAL", "Fernanda")

# -------- Aliases de compatibilidade (se você tiver nomes diferentes internamente) --------
# Por exemplo, se em alguma versão você chamou de append_rows_safe, mantenha:
try:
    from . import append_rows_safe as _append_internal  # se tiver pacote
except Exception:
    _append_internal = None

if _append_internal and _append_internal is not append_rows:
    # redireciona a API pública para a interna
    append_rows = _append_internal  # noqa: E305

# Delimite a interface pública:
__all__ = ["connect", "read_ws", "append_rows", "new_id", "default_profissional"]
