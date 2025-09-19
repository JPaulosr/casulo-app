# utils_casulo.py
# Utilitários de conexão e escrita/leitura no Google Sheets para o app Casulo

from __future__ import annotations
import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# ---------------------------
# Config (lidos de st.secrets)
# ---------------------------
PLANILHA_URL = (st.secrets.get("PLANILHA_URL", "") or "").strip()

def _normalize_private_key(pk: str) -> str:
    """Conserta quebras de linha escapadas de chaves do service account."""
    if not pk:
        return pk
    return pk.replace("\\n", "\n").strip()

# --------------------------------
# Conexão cacheada ao Spreadsheet
# --------------------------------
@st.cache_resource(show_spinner=False)
def connect():
    """
    Conecta ao Google Sheets com o service account do st.secrets["GCP_SERVICE_ACCOUNT"]
    e retorna o objeto Spreadsheet já aberto via URL.
    """
    if not PLANILHA_URL:
        raise RuntimeError("PLANILHA_URL ausente em st.secrets.")
    sa = dict(st.secrets["GCP_SERVICE_ACCOUNT"])  # cópia mutável
    sa["private_key"] = _normalize_private_key(sa.get("private_key", ""))

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa, scopes=scopes)
    gc = gspread.authorize(creds)
    ss = gc.open_by_url(PLANILHA_URL)
    return ss

# --------------------------------
# Helpers de cabeçalho/append seguro
# --------------------------------
def ensure_headers(ws, desired_headers: list[str]) -> list[str]:
    """
    Garante que a 1ª linha da aba contenha (pelo menos) desired_headers.
    Acrescenta as que faltarem mantendo as existentes.
    Retorna a lista final de cabeçalhos.
    """
    headers = ws.row_values(1)
    if not headers:
        ws.update("1:1", [desired_headers])
        return desired_headers[:]

    # remove duplicados mantendo ordem
    seen = set()
    fixed = []
    for h in headers:
        h = (h or "").strip()
        if not h or h in seen:
            continue
        seen.add(h)
        fixed.append(h)

    # adiciona faltantes
    for h in desired_headers:
        if h not in fixed:
            fixed.append(h)

    if fixed != headers:
        ws.update("1:1", [fixed])

    return fixed

def append_rows(ws, dicts: list[dict], default_headers: list[str] | None = None):
    """
    Append de linhas a partir de uma lista de dicionários, respeitando a ordem do cabeçalho.
    Se a aba estiver vazia, usa default_headers como cabeçalho (ou união das chaves).
    """
    headers = ws.row_values(1)
    if not headers:
        if default_headers:
            headers = default_headers[:]
        else:
            # união ordenada de todas as chaves
            keys = []
            seen = set()
            for d in dicts:
                for k in d.keys():
                    if k not in seen:
                        seen.add(k)
                        keys.append(k)
            headers = keys
        ws.update("1:1", [headers])

    # mapeia dicionários para a ordem do cabeçalho
    rows = []
    for d in dicts:
        row = [d.get(h, "") for h in headers]
        rows.append(row)

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

# --------------------------------
# Leitura robusta de worksheets
# --------------------------------
def read_ws(ss, title: str, expected_headers: list[str] | None = None, rows=2000, cols=50):
    """
    Abre (ou cria) uma worksheet por título e devolve (df, ws).

    - Cria a aba com expected_headers se não existir.
    - Tenta ler com evaluate_formulas=True; se der APIError, tenta sem.
    - Garante colunas esperadas no DataFrame (cria vazias e reordena).
    """
    try:
        try:
            ws = ss.worksheet(title)
        except WorksheetNotFound:
            ws = ss.add_worksheet(title=title, rows=rows, cols=max(cols, len(expected_headers or [])))
            if expected_headers:
                ws.update("1:1", [expected_headers])

        # 1ª tentativa: com evaluate_formulas
        try:
            df = get_as_dataframe(ws, evaluate_formulas=True, header=0).fillna("")
        except APIError:
            # 2ª tentativa: sem evaluate_formulas
            df = get_as_dataframe(ws, evaluate_formulas=False, header=0).fillna("")

        # Normaliza colunas esperadas
        if expected_headers:
            for h in expected_headers:
                if h not in df.columns:
                    df[h] = ""
            df = df[expected_headers]

        return df, ws

    except APIError as e:
        with st.expander("Detalhes técnicos (Google Sheets)", expanded=False):
            st.write(str(e))
        st.error(
            f"Não consegui ler a aba **{title}** na planilha.\n\n"
            "Verifique:\n"
            "• Se o arquivo/URL em `PLANILHA_URL` está correto;\n"
            "• Se a planilha está compartilhada com o service account (Editor);\n"
            "• Se a aba existe com esse nome exato.\n"
        )
        return pd.DataFrame(columns=(expected_headers or [])), None

# --------------------------------
# Geração de IDs
# --------------------------------
@st.cache_data(show_spinner=False)
def _tz() -> pytz.timezone:
    tz_name = st.secrets.get("TZ", "America/Sao_Paulo")
    try:
        return pytz.timezone(tz_name)
    except Exception:
        return pytz.timezone("America/Sao_Paulo")

def new_id(prefix: str = "R") -> str:
    """
    Gera ID com timestamp local, ex.: R-20250919T143015123
    """
    now = datetime.now(_tz())
    return f"{prefix}-{now.strftime('%Y%m%d%H%M%S%f')[:-3]}"
