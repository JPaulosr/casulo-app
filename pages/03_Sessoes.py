# pages/03_Sessoes.py
import streamlit as st
from datetime import date
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Sessões", page_icon="📅", layout="wide")
st.title("📅 Sessões")

ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email","Diagnostico",
            "Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, ws = read_ws(ss, "Sessoes", SES_COLS)

st.subheader("Agenda simples")
st.dataframe(df_ses[["Data","HoraInicio","PacienteID","Profissional","Status","Tipo"]], use_container_width=True, hide_index=True)

st.subheader("Registrar/Agendar")
with st.form("nova_sessao"):
    pid = st.selectbox("Paciente", df_pac["PacienteID"].astype(str).tolist())
    data = st.date_input("Data", value=date.today())
    hi = st.text_input("Hora início (HH:MM)", "")
    hf = st.text_input("Hora fim (HH:MM)", "")
    prof = st.text_input("Profissional", "Terapeuta")
    status = st.selectbox("Status", ["Agendada","Realizada","Falta","Cancelada"], index=0)
    tipo = st.selectbox("Tipo", ["Terapia", "Avaliação", "Retorno"], index=0)
    objetivos = st.text_input("Objetivos trabalhados (resumo)", "")
    obs = st.text_area("Observações", "")
    anexos = st.text_input("AnexosURL (opcional)", "")
    ok = st.form_submit_button("Salvar")
    if ok:
        sid = new_id("S")
        append_rows(ws, [{
            "SessaoID": sid, "PacienteID": pid, "Data": data.strftime("%d/%m/%Y"),
            "HoraInicio": hi, "HoraFim": hf, "Profissional": prof, "Status": status, "Tipo": tipo,
            "ObjetivosTrabalhados": objetivos, "Observacoes": obs, "AnexosURL": anexos
        }], default_headers=SES_COLS)
        st.success(f"Sessão salva ({sid})")
        st.cache_data.clear()
