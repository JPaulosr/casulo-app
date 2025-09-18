# pages/03_Sessoes.py
import streamlit as st
from datetime import date, datetime
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Sessões", page_icon="📅", layout="wide")
st.title("📅 Sessões")

# ---------------- helpers ----------------
def parse_hhmm(txt: str):
    try:
        return datetime.strptime(str(txt).strip(), "%H:%M").time()
    except Exception:
        return None

def to_min(t):
    return t.hour * 60 + t.minute if t else None

def overlap(a_ini, a_fim, b_ini, b_fim) -> bool:
    """Retorna True se [a_ini,a_fim) e [b_ini,b_fim) se sobrepõem.
       Se algum fim vier None, considera igualdade de início como conflito."""
    if a_ini is None or b_ini is None:
        return False
    if a_fim is None or b_fim is None:
        return to_min(a_ini) == to_min(b_ini)
    return not (to_min(a_fim) <= to_min(b_ini) or to_min(a_ini) >= to_min(b_fim))

# ---------------- dados ----------------
ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, ws = read_ws(ss, "Sessoes", SES_COLS)

# ---------------- lista simples ----------------
if not df_ses.empty:
    df_show = df_ses.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
    st.subheader("Agenda simples")
    st.dataframe(
        df_show[["Data","HoraInicio","Nome","Profissional","Status","Tipo"]],
        use_container_width=True, hide_index=True
    )
else:
    st.info("Sem sessões registradas ainda.")

# ---------------- formulário ----------------
st.subheader("Registrar/Agendar")
with st.form("nova_sessao"):
    nomes = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
    nome_sel = st.selectbox("Paciente", nomes)
    pid = (
        df_pac.loc[df_pac["Nome"].astype(str).str.strip() == nome_sel, "PacienteID"]
        .astype(str).iloc[0] if nome_sel else ""
    )
    data_sel = st.date_input("Data", value=date.today())
    hi_txt = st.text_input("Hora início (HH:MM)", "")
    hf_txt = st.text_input("Hora fim (HH:MM)", "")
    prof = st.text_input("Profissional", "Terapeuta")
    status = st.selectbox("Status", ["Agendada","Realizada","Falta","Cancelada"], index=0)
    tipo = st.selectbox("Tipo", ["Terapia", "Avaliação", "Retorno"], index=0)
    objetivos = st.text_input("Objetivos trabalhados (resumo)", "")
    obs = st.text_area("Observações", "")
    anexos = st.text_input("AnexosURL (opcional)", "")

    ok = st.form_submit_button("Salvar")

if ok:
    # validações básicas
    if not pid:
        st.error("Selecione um paciente.")
        st.stop()

    hi = parse_hhmm(hi_txt)
    hf = parse_hhmm(hf_txt) if hf_txt.strip() else None

    if not hi:
        st.error("Informe **Hora início** no formato HH:MM (ex.: 14:30).")
        st.stop()
    if hf and to_min(hf) <= to_min(hi):
        st.error("**Hora fim** deve ser maior que a **Hora início**.")
        st.stop()

    data_str = data_sel.strftime("%d/%m/%Y")

    # --- trava anti-duplicidade (mesmo paciente e mesmo dia)
    mesmo_dia = df_ses[
        (df_ses["PacienteID"].astype(str) == pid) &
        (df_ses["Data"].astype(str).str.strip() == data_str)
    ].copy()

    conflitos = []
    if not mesmo_dia.empty:
        for _, r in mesmo_dia.iterrows():
            e_hi = parse_hhmm(r.get("HoraInicio", ""))
            e_hf = parse_hhmm(r.get("HoraFim", "")) if str(r.get("HoraFim","")).strip() else None

            # ignora canceladas? comente a linha abaixo se quiser considerar
            if str(r.get("Status","")).strip().lower() == "cancelada":
                continue

            if overlap(hi, hf, e_hi, e_hf):
                conflitos.append({
                    "Data": data_str,
                    "HoraInicio": r.get("HoraInicio",""),
                    "HoraFim": r.get("HoraFim",""),
                    "Profissional": r.get("Profissional",""),
                    "Tipo": r.get("Tipo",""),
                    "Status": r.get("Status",""),
                })

    if conflitos:
        st.error("⚠️ Conflito de horário: já existe sessão para este paciente nesse intervalo.")
        st.dataframe(conflitos, use_container_width=True, hide_index=True)
        st.stop()

    # --- gravação
    sid = new_id("S")
    append_rows(ws, [{
        "SessaoID": sid,
        "PacienteID": pid,
        "Data": data_str,
        "HoraInicio": hi_txt.strip(),
        "HoraFim": hf_txt.strip(),
        "Profissional": prof.strip(),
        "Status": status.strip(),
        "Tipo": tipo.strip(),
        "ObjetivosTrabalhados": objetivos.strip(),
        "Observacoes": obs.strip(),
        "AnexosURL": anexos.strip()
    }], default_headers=SES_COLS)

    st.success(f"Sessão salva para **{nome_sel}** ({sid})")
    st.cache_data.clear()
    st.rerun()
