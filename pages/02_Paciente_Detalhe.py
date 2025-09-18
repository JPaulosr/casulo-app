# pages/02_Paciente_Detalhe.py
import streamlit as st
import pandas as pd
from utils_casulo import connect, read_ws, foto_map

st.set_page_config(page_title="Casulo — Paciente", page_icon="📄", layout="wide")
st.title("📄 Detalhe do Paciente")

ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email","Diagnostico",
            "Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
OBJ_COLS = ["ObjetivoID","PacienteID","Categoria","Descricao","NivelAtual(0-100)","ProximaMeta","UltimaRevisao"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes", SES_COLS)
df_obj, _ = read_ws(ss, "Objetivos", OBJ_COLS)
df_pag, _ = read_ws(ss, "Pagamentos", PAG_COLS)

pid = st.selectbox("Escolha o PacienteID", [""] + df_pac["PacienteID"].astype(str).tolist())
if not pid:
    st.info("Selecione um paciente.")
    st.stop()

p = df_pac[df_pac["PacienteID"]==pid].head(1)
if p.empty:
    st.warning("Paciente não encontrado.")
    st.stop()
p = p.iloc[0]

col1, col2 = st.columns([1,3])
with col1:
    if p.get("FotoURL",""):
        st.image(p["FotoURL"], caption=p.get("Nome",""), width=220)
with col2:
    st.markdown(f"### {p.get('Nome','')}")
    st.write(f"**Responsável:** {p.get('Responsavel','-')}  |  **Telefone:** {p.get('Telefone','-')}")
    st.write(f"**Diagnóstico:** {p.get('Diagnostico','-')}")
    st.write(f"**Convênio:** {p.get('Convenio','-')}  |  **Status:** {p.get('Status','-')}  |  **Prioridade:** {p.get('Prioridade','-')}")
    st.caption(p.get("Observacoes",""))

st.divider()
tab_obj, tab_ses, tab_fin, tab_docs = st.tabs(["🎯 Objetivos","📝 Sessões","💰 Financeiro","📎 Documentos"])

with tab_obj:
    objs = df_obj[df_obj["PacienteID"]==pid].copy()
    st.dataframe(objs, use_container_width=True, hide_index=True)

with tab_ses:
    ses = df_ses[df_ses["PacienteID"]==pid].copy()
    st.dataframe(ses[["Data","HoraInicio","HoraFim","Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes"]], use_container_width=True, hide_index=True)

with tab_fin:
    fin = df_pag[df_pag["PacienteID"]==pid].copy()
    st.dataframe(fin[["Data","Forma","Bruto","Liquido","TaxaValor","Referencia","Obs"]], use_container_width=True, hide_index=True)

with tab_docs:
    # se quiser separar em uma aba "Documentos" na planilha
    st.info("Anexe links de documentos na aba Documentos (URL). Podemos integrar upload depois.")
