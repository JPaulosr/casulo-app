# pages/03_Sessoes.py
import streamlit as st
from datetime import date, datetime, timedelta, time
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Sessões", page_icon="📅", layout="wide")
st.title("📅 Sessões")

# ================= helpers =================
def parse_hhmm(txt: str):
    try:
        return datetime.strptime(str(txt).strip(), "%H:%M").time()
    except Exception:
        return None

def to_min(t: time | None):
    return t.hour * 60 + t.minute if t else None

def overlap(a_ini, a_fim, b_ini, b_fim) -> bool:
    """True se [a_ini,a_fim) e [b_ini,b_fim) se sobrepõem.
       Se algum fim for None, considera conflito quando o início for igual."""
    if a_ini is None or b_ini is None:
        return False
    if a_fim is None or b_fim is None:
        return to_min(a_ini) == to_min(b_ini)
    return not (to_min(a_fim) <= to_min(b_ini) or to_min(a_ini) >= to_min(b_fim))

def br_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def week_bounds(anchor: date):
    start = anchor - timedelta(days=anchor.weekday())  # Monday
    end = start + timedelta(days=6)                    # Sunday
    return start, end

WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# ================= dados =================
ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, ws = read_ws(ss, "Sessoes", SES_COLS)

# ================= agenda semanal (calendário) =================
st.subheader("🗓️ Agenda (semana)")

# navegação de semanas
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0
col_prev, col_today, col_next = st.columns(3)
if col_prev.button("← Semana anterior", use_container_width=True):
    st.session_state.week_offset -= 1
    st.rerun()
if col_today.button("Hoje", use_container_width=True):
    st.session_state.week_offset = 0
    st.rerun()
if col_next.button("Próxima semana →", use_container_width=True):
    st.session_state.week_offset += 1
    st.rerun()

anchor = date.today() + timedelta(weeks=st.session_state.week_offset)
ini_sem, fim_sem = week_bounds(anchor)
st.caption(f"Semana: **{br_date(ini_sem)} → {br_date(fim_sem)}**")

# filtra sessões no intervalo
def _to_date(s):
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None

df_ses["__d"] = df_ses["Data"].apply(_to_date)
semana = df_ses[(df_ses["__d"] >= ini_sem) & (df_ses["__d"] <= fim_sem)].copy()
semana = semana.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")

# tenta exibir com plotly timeline; se não tiver plotly, lista simples
try:
    import plotly.express as px
    import pandas as pd

    if not semana.empty:
        # cria colunas de datetime para início/fim
        def _dt(row):
            d = row["__d"] or ini_sem
            hi = parse_hhmm(row.get("HoraInicio","")) or time(0,0)
            hf = parse_hhmm(row.get("HoraFim",""))
            if not hf:
                # assume 50 min se não informar fim
                hf_dt = datetime.combine(d, hi) + timedelta(minutes=50)
            else:
                hf_dt = datetime.combine(d, hf)
            return datetime.combine(d, hi), hf_dt

        starts, ends = zip(*semana.apply(_dt, axis=1))
        semana["__start"] = list(starts)
        semana["__end"]   = list(ends)
        semana["__day"]   = semana["__d"].apply(lambda d: WEEKDAYS_PT[d.weekday()] if d else "-")
        semana["__label"] = semana.apply(
            lambda r: f"{r.get('Nome','-')} • {r.get('Profissional','') or 'Prof.'} • {r.get('Tipo','') or ''}",
            axis=1
        )

        fig = px.timeline(
            semana,
            x_start="__start",
            x_end="__end",
            y="__day",
            color="Nome",
            hover_data={"Data":True,"HoraInicio":True,"HoraFim":True,"Profissional":True,"Status":True,"Tipo":True},
            custom_data=["__label"]
        )
        fig.update_yaxes(categoryorder='array', categoryarray=WEEKDAYS_PT)  # mantém ordem seg→dom
        fig.update_layout(height=420, showlegend=True, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem sessões nesta semana.")
except Exception:
    # fallback em lista por dia
    if semana.empty:
        st.info("Sem sessões nesta semana.")
    else:
        for i in range(7):
            dia = ini_sem + timedelta(days=i)
            dd = semana[semana["__d"] == dia].copy()
            if dd.empty:
                continue
            st.markdown(f"**{WEEKDAYS_PT[dia.weekday()]} — {br_date(dia)}**")
            dd = dd.sort_values("HoraInicio")
            cols = ["HoraInicio","HoraFim","Nome","Profissional","Tipo","Status"]
            cols = [c for c in cols if c in dd.columns]
            st.dataframe(dd[cols], use_container_width=True, hide_index=True)

st.divider()

# ================= tabs: pontual x recorrente =================
tab_pontual, tab_rec = st.tabs(["📝 Agendar pontual", "🔁 Agendar recorrente (semanal)"])

# ---------- Agendar pontual ----------
with tab_pontual:
    with st.form("nova_sessao_pontual"):
        nomes = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
        nome_sel = st.selectbox("Paciente", nomes)
        pid = (
            df_pac.loc[df_pac["Nome"].astype(str).str.strip() == nome_sel, "PacienteID"]
            .astype(str).iloc[0] if nome_sel else ""
        )
        data_sel = st.date_input("Data", value=date.today(), key="pont_data")
        hi_txt = st.text_input("Hora início (HH:MM)", key="pont_hi")
        hf_txt = st.text_input("Hora fim (HH:MM)", key="pont_hf")
        prof = st.text_input("Profissional", "Terapeuta", key="pont_prof")
        status = st.selectbox("Status", ["Agendada","Realizada","Falta","Cancelada"], index=0, key="pont_status")
        tipo = st.selectbox("Tipo", ["Terapia", "Avaliação", "Retorno"], index=0, key="pont_tipo")
        objetivos = st.text_input("Objetivos trabalhados (resumo)", key="pont_obj")
        obs = st.text_area("Observações", key="pont_obs")
        anexos = st.text_input("AnexosURL (opcional)", key="pont_anexos")
        ok = st.form_submit_button("Salvar")

    if ok:
        if not pid:
            st.error("Selecione um paciente."); st.stop()
        hi = parse_hhmm(hi_txt); hf = parse_hhmm(hf_txt) if hf_txt.strip() else None
        if not hi: st.error("Informe **Hora início** em HH:MM."); st.stop()
        if hf and to_min(hf) <= to_min(hi): st.error("**Hora fim** > **Hora início**."); st.stop()

        data_str = br_date(data_sel)

        # trava duplicidade nesse paciente/dia
        mesmo_dia = df_ses[
            (df_ses["PacienteID"].astype(str) == pid) &
            (df_ses["Data"].astype(str).str.strip() == data_str)
        ].copy()

        conflitos = []
        if not mesmo_dia.empty:
            for _, r in mesmo_dia.iterrows():
                e_hi = parse_hhmm(r.get("HoraInicio",""))
                e_hf = parse_hhmm(r.get("HoraFim","")) if str(r.get("HoraFim","")).strip() else None
                if str(r.get("Status","")).strip().lower() == "cancelada":  # ignore canceladas
                    continue
                if overlap(hi, hf, e_hi, e_hf):
                    conflitos.append(r)

        if conflitos:
            st.error("⚠️ Conflito de horário para este paciente nesse dia.")
            st.stop()

        sid = new_id("S")
        append_rows(ws, [{
            "SessaoID": sid, "PacienteID": pid, "Data": data_str,
            "HoraInicio": hi_txt.strip(), "HoraFim": hf_txt.strip(),
            "Profissional": prof.strip(), "Status": status.strip(), "Tipo": tipo.strip(),
            "ObjetivosTrabalhados": objetivos.strip(), "Observacoes": obs.strip(), "AnexosURL": anexos.strip()
        }], default_headers=SES_COLS)
        st.success(f"Sessão salva para **{nome_sel}** ({sid})")
        st.cache_data.clear(); st.rerun()

# ---------- Agendar recorrente (semanal) ----------
with tab_rec:
    with st.form("nova_recorrencia"):
        nomes_r = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
        nome_r = st.selectbox("Paciente", nomes_r, key="rec_nome")
        pid_r = (
            df_pac.loc[df_pac["Nome"].astype(str).str.strip() == nome_r, "PacienteID"]
            .astype(str).iloc[0] if nome_r else ""
        )

        col_a, col_b = st.columns([1,1])
        with col_a:
            dias_semana = st.multiselect(
                "Dia(s) da semana",
                options=list(range(7)),
                default=[1],            # terça por padrão
                format_func=lambda i: WEEKDAYS_PT[i]
            )
            hi_r = st.text_input("Hora início (HH:MM)", "15:00", key="rec_hi")
            hf_r = st.text_input("Hora fim (HH:MM)", "15:50", key="rec_hf")
        with col_b:
            data_ini = st.date_input("Início (primeira semana)", value=date.today(), key="rec_ini")
            semanas = st.number_input("Repetir por (semanas)", min_value=1, max_value=52, value=12, step=1, key="rec_rep")
            prof_r = st.text_input("Profissional", "Terapeuta", key="rec_prof")

        status_r = st.selectbox("Status padrão", ["Agendada","Realizada","Falta","Cancelada"], index=0, key="rec_status")
        tipo_r   = st.selectbox("Tipo", ["Terapia","Avaliação","Retorno"], index=0, key="rec_tipo")
        obs_r    = st.text_input("Observações (aplicadas a todas)", "Recorrente", key="rec_obs")

        ok_rec = st.form_submit_button("Criar sessões recorrentes")

    if ok_rec:
        if not pid_r:
            st.error("Selecione um paciente."); st.stop()
        hi = parse_hhmm(hi_r); hf = parse_hhmm(hf_r) if hf_r.strip() else None
        if not hi: st.error("Hora início inválida."); st.stop()
        if hf and to_min(hf) <= to_min(hi): st.error("**Hora fim** > **Hora início**."); st.stop()
        if not dias_semana: st.error("Escolha ao menos um dia da semana."); st.stop()

        criadas, puladas = [], []

        # gera as semanas
        start_week, _ = week_bounds(data_ini)
        for w in range(semanas):
            base = start_week + timedelta(weeks=w)
            for dow in sorted(dias_semana):
                d = base + timedelta(days=dow)
                data_str = br_date(d)

                # verifica conflito no mesmo paciente/dia
                mesmo_dia = df_ses[
                    (df_ses["PacienteID"].astype(str) == pid_r) &
                    (df_ses["Data"].astype(str).str.strip() == data_str)
                ].copy()

                tem_conflito = False
                if not mesmo_dia.empty:
                    for _, r in mesmo_dia.iterrows():
                        e_hi = parse_hhmm(r.get("HoraInicio",""))
                        e_hf = parse_hhmm(r.get("HoraFim","")) if str(r.get("HoraFim","")).strip() else None
                        if str(r.get("Status","")).strip().lower() == "cancelada":
                            continue
                        if overlap(hi, hf, e_hi, e_hf):
                            tem_conflito = True; break

                if tem_conflito:
                    puladas.append((d, r.get("HoraInicio",""), r.get("HoraFim","")))
                    continue

                criadas.append({
                    "SessaoID": new_id("S"),
                    "PacienteID": pid_r,
                    "Data": data_str,
                    "HoraInicio": hi_r.strip(),
                    "HoraFim": hf_r.strip(),
                    "Profissional": prof_r.strip(),
                    "Status": status_r.strip(),
                    "Tipo": tipo_r.strip(),
                    "ObjetivosTrabalhados": "",
                    "Observacoes": obs_r.strip(),
                    "AnexosURL": ""
                })

        if not criadas:
            st.warning("Nenhuma sessão criada (todas conflitaram?).")
            if puladas:
                st.caption(f"Puladas por conflito: {len(puladas)}")
            st.stop()

        # grava em lote
        append_rows(ws, criadas, default_headers=SES_COLS)
        st.success(f"✅ Criadas {len(criadas)} sessões recorrentes para **{nome_r}**.")
        if puladas:
            st.info(f"⚠️ {len(puladas)} data(s) ignoradas por conflito.")
        st.cache_data.clear(); st.rerun()
