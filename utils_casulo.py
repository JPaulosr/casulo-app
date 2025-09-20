# utils_casulo.py — Núcleo compatível p/ todas as páginas

from __future__ import annotations

import time
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe


# =========================
# Helpers internos
# =========================
def _normalize_private_key(pkey: str) -> str:
    """Conserta quebras de linha de chaves copiadas como string única."""
    if isinstance(pkey, str):
        return pkey.replace("\\n", "\n")
    return pkey


def _get_ss() -> gspread.Spreadsheet:
    """
    Abre o Spreadsheet a partir de st.secrets:
      - PLANILHA_URL: pode ser URL completa OU apenas o ID
      - [gcp_service_account]: bloco com as credenciais
    """
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

    # Aceita URL completa ou apenas ID
    if planilha_ref.startswith("http"):
        return gc.open_by_url(planilha_ref)
    return gc.open_by_key(planilha_ref)


# =========================
# API pública estável
# =========================
@st.cache_resource(show_spinner="Conectando ao Google Sheets…")
def connect() -> gspread.Spreadsheet:
    """Retorna o Spreadsheet (gspread.Spreadsheet)."""
    try:
        return _get_ss()
    except gspread.exceptions.APIError as e:
        sa = st.secrets.get("gcp_service_account", {})
        st.error(
            "❌ Não consegui abrir a planilha pelo Google API.\n\n"
            "Checklist rápido:\n"
            "1) Compartilhe a planilha com o e-mail do Service Account (Editor):\n"
            f"   {sa.get('client_email', '(sem email)')}\n"
            "2) Em secrets, 'PLANILHA_URL' pode ser a URL COMPLETA ou o ID correto.\n"
            "3) A planilha existe e está acessível.\n\n"
            f"Detalhe técnico: {e}"
        )
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {e}")
        st.stop()


def read_ws(ss: gspread.Spreadsheet, title: str, expected_cols: list[str] | None = None) -> tuple[pd.DataFrame, gspread.Worksheet]:
    """
    Lê (ou cria) a worksheet `title`.
    - Se não existir, cria com as colunas de `expected_cols`.
    - Retorna (df: DataFrame[str], ws: gspread.Worksheet)
    - O DataFrame vem normalizado para conter exatamente `expected_cols` quando fornecido.
    """
    try:
        ws = ss.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        cols = max(len(expected_cols or []), 1)
        ws = ss.add_worksheet(title=title, rows=1, cols=cols)
        if expected_cols:
            # cria header
            set_with_dataframe(ws, pd.DataFrame(columns=expected_cols), include_index=False)

    df = get_as_dataframe(ws, evaluate_formulas=False, dtype=str)

    # Normaliza colunas na ordem esperada (quando fornecida)
    if expected_cols:
        if df is None or df.empty:
            df = pd.DataFrame(columns=expected_cols, dtype=str)
        else:
            # reindexa SEM perder colunas extras (mantém apenas as esperadas)
            df = df.reindex(columns=expected_cols)

    # Higieniza NaN -> "" (string) para evitar erros no Streamlit
    if df is None:
        df = pd.DataFrame(columns=(expected_cols or []))
    else:
        df = df.fillna("")

    return df, ws


def append_rows(ws: gspread.Worksheet, rows, default_headers: list[str] | None = None) -> bool:
    """
    Append seguro: aceita lista de dicts OU lista de listas.
    - Se a planilha estiver vazia e houver `default_headers`, escreve o header.
    - Reescreve a planilha inteira (gspread_dataframe) para evitar desalinhamento.
    """
    df_atual = get_as_dataframe(ws, evaluate_formulas=False, dtype=str)
    if df_atual is None or df_atual.empty:
        if default_headers:
            set_with_dataframe(ws, pd.DataFrame(columns=default_headers), include_index=False)
            df_atual = pd.DataFrame(columns=default_headers)
        else:
            df_atual = pd.DataFrame()

    # Caso entrada seja lista de dicts -> alinhar chaves às colunas existentes
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        cols = list(df_atual.columns) if len(df_atual.columns) else (default_headers or sorted({k for r in rows for k in r.keys()}))
        novos = pd.DataFrame(rows)
        for c in cols:
            if c not in novos.columns:
                novos[c] = ""
        novos = novos[cols]
    else:
        # Assume listas alinhadas às colunas existentes ou default_headers
        cols = list(df_atual.columns) if len(df_atual.columns) else (default_headers or [])
        novos = pd.DataFrame(rows, columns=cols if cols else None)

    # Garantir strings e substituir NaN
    df_out = pd.concat([df_atual, novos], ignore_index=True).fillna("")
    set_with_dataframe(ws, df_out, include_index=False)
    return True


def new_id(prefix: str = "R") -> str:
    """ID curto com prefixo + timestamp (ms)."""
    return f"{prefix}-{int(time.time() * 1000)}"


def default_profissional() -> str:
    """Nome padrão do profissional (para páginas que usam)."""
    return st.secrets.get("DEFAULT_PROFISSIONAL", "Fernanda")


# =========================
# Aliases de compatibilidade (se você tiver nomes diferentes internamente)
# =========================
try:
    from . import append_rows_safe as _append_internal  # se estiver usando como pacote
except Exception:
    _append_internal = None

if _append_internal and _append_internal is not append_rows:
    append_rows = _append_internal  # redireciona API pública


# Limita o que será importado via `from utils_casulo import *`
__all__ = ["connect", "read_ws", "append_rows", "new_id", "default_profissional"]
