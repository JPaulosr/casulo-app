# utils_casulo.py
import streamlit as st
import pandas as pd
from gspread_dataframe import get_as_dataframe
from gspread.exceptions import WorksheetNotFound, APIError

# ... (demais imports e funções que você já tem)

def read_ws(ss, title: str, expected_headers: list[str] | None = None, rows=2000, cols=50):
    """
    Abre (ou cria) uma worksheet por título e devolve (df, ws).
    - Se a aba não existir, cria com o cabeçalho (se fornecido).
    - Tenta ler com evaluate_formulas=True; se der APIError, tenta sem.
    - Garante que todas as colunas em expected_headers existam no df.
    """
    try:
        try:
            ws = ss.worksheet(title)
        except WorksheetNotFound:
            ws = ss.add_worksheet(title=title, rows=rows, cols=max(cols, len(expected_headers or [])))
            if expected_headers:
                ws.update('1:1', [expected_headers])

        # 1ª tentativa: com evaluate_formulas
        try:
            df = get_as_dataframe(ws, evaluate_formulas=True, header=0).fillna("")
        except APIError:
            # 2ª tentativa: sem evaluate_formulas (algumas fórmulas quebram)
            df = get_as_dataframe(ws, evaluate_formulas=False, header=0).fillna("")

        # Normaliza colunas
        if expected_headers:
            # cria colunas faltantes
            for h in expected_headers:
                if h not in df.columns:
                    df[h] = ""
            # reordena
            df = df[expected_headers]

        return df, ws

    except APIError as e:
        # mensagem mais amigável
        with st.expander("Detalhes técnicos (Google Sheets)", expanded=False):
            st.write(str(e))
        st.error(
            f"Não consegui ler a aba **{title}** na planilha.\n\n"
            "Verifique:\n"
            "• Se o arquivo/URL em `PLANILHA_URL` está correto;\n"
            "• Se a planilha está compartilhada com o service account (Editor);\n"
            "• Se a aba existe com esse nome exato.\n"
        )
        # devolve DF vazio para não derrubar a página
        df_vazio = pd.DataFrame(columns=(expected_headers or []))
        return df_vazio, None
