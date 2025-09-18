# pages/00_Cadastrar_Paciente.py
import streamlit as st
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Cadastrar Paciente", page_icon="📝", layout="wide")
st.title("📝 Cadastrar Paciente")

ss = connect()

PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]
_, ws_pac = read_ws(ss, "Pacientes", PAC_COLS)

st.info("Campos com * são obrigatórios. Datas no formato **DD/MM/AAAA**.")

with st.form("form_cadastro_paciente", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Nome completo*", "")
        nasc = st.text_input("Data de nascimento (DD/MM/AAAA)", "")
        resp = st.text_input("Responsável", "")
        tel  = st.text_input("Telefone/WhatsApp", "")
        email= st.text_input("E-mail", "")
        conv = st.text_input("Convênio (ou 'Particular')", "Particular")
    with c2:
        diag = st.text_area("Diagnóstico(s) / observações clínicas", "")
        status = st.selectbox("Status*", ["Ativo","Pausa","Alta"], index=0)
        prio = st.selectbox("Prioridade", ["Normal","Alta","Urgente"], index=0)
        foto = st.text_input("FotoURL (Drive/Cloudinary)", "")
        obs  = st.text_area("Observações adicionais", "")

    salvar = st.form_submit_button("Salvar paciente", use_container_width=True)

if salvar:
    if not nome.strip():
        st.error("Informe o **Nome**.")
        st.stop()
    pid = new_id("P")
    append_rows(ws_pac, [{
        "PacienteID": pid, "Nome": nome.strip(), "DataNascimento": nasc.strip(),
        "Responsavel": resp.strip(), "Telefone": tel.strip(), "Email": email.strip(),
        "Diagnostico": diag.strip(), "Convenio": conv.strip(), "Status": status.strip(),
        "Prioridade": prio.strip(), "FotoURL": foto.strip(), "Observacoes": obs.strip(),
    }], default_headers=PAC_COLS)
    st.success(f"✅ Paciente cadastrado: **{nome}** (ID: {pid})")
    st.cache_data.clear()
    st.button("Cadastrar outro", on_click=lambda: st.experimental_rerun())
