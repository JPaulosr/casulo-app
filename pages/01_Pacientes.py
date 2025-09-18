
# pages/01_Pacientes.py
import streamlit as st
import pandas as pd
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Pacientes", page_icon="👨‍👩‍👧", layout="wide")
st.title("👨‍👩‍👧 Pacientes")

ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email","Diagnostico",
            "Convenio","Status","Prioridade","FotoURL","Observacoes"]
df, ws = read_ws(ss, "Pacientes", PAC_COLS)

st.subheader("Lista")
st.dataframe(df[["PacienteID","Nome","Responsavel","Telefone","Status","Prioridade"]], use_container_width=True, hide_index=True)

st.subheader("Cadastrar novo")
with st.form("novo_paciente"):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Nome*", "")
        nasc = st.text_input("Data de nascimento (DD/MM/AAAA)", "")
        resp = st.text_input("Responsável", "")
        tel  = st.text_input("Telefone", "")
        email= st.text_input("Email", "")
        conv = st.text_input("Convênio (ou 'Particular')", "")
    with c2:
        diag = st.text_area("Diagnóstico(s)", "")
        status = st.selectbox("Status", ["Ativo","Pausa","Alta"], index=0)
        prio = st.selectbox("Prioridade", ["Normal","Alta","Urgente"], index=0)
        foto = st.text_input("FotoURL (Drive/Cloudinary)", "")
        obs  = st.text_area("Observações", "")
    ok = st.form_submit_button("Salvar")
    if ok:
        pid = new_id("P")
        append_rows(ws, [{
            "PacienteID": pid, "Nome": nome, "DataNascimento": nasc,
            "Responsavel": resp, "Telefone": tel, "Email": email,
            "Diagnostico": diag, "Convenio": conv, "Status": status,
            "Prioridade": prio, "FotoURL": foto, "Observacoes": obs
        }], default_headers=PAC_COLS)
        st.success(f"Paciente cadastrado: {nome} ({pid})")
        st.cache_data.clear()
