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
    if a_ini is None or b_ini is None:
        return False
    if a_fim is None or b_fim is None:
        return to_min(a_ini) == to_min(b_ini)
    return not (to_min(a_fim) <= to_min(b_ini) or to_min(a_ini) >= to_min(b_fim))

def br_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def parse_br_date(s: str):
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None

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

# mapeia header -> índice de coluna (para update)
headers = ws.row_values(1)
col_idx = {h: i+1 for i, h in enumerate(headers)}  # 1-based

# coluna auxiliar com número da linha na planilha
df_ses = df_ses.copy()
df_ses["__rownum"] = df_ses.index + 2  # header é linha 1 na planilha
df_ses["__d"] = df_ses["Data"].apply(parse_br_date)

# ================= agenda semanal (calendário) =================
st.subheader("🗓️ Agenda (semana)")

if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0
c_prev, c_today, c_next = st.columns(3)
if c_prev.button("← Semana anterior", use_container_width=True):
    st.session_state.week_offset -= 1; st.rerun()
if c_today.button("Hoje", use_container_width=True):
    st.session_state.week_offset = 0; st.rerun()
if c_next.button("Próxima semana →", use_container_width=True):
    st.session_state.week_offset += 1; st.rerun()

anchor = date.today() + timedelta(weeks=st.session_state.week_offset)
ini_sem, fim_sem = week_bounds(anchor)
st.caption(f"Semana: **{br_date(ini_sem)} → {br_date(fim_sem)}**")

semana = df_ses[(df_ses["__d"] >= ini_sem) & (df_ses["__d"] <= fim_sem)].copy()
semana = semana.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")

# tenta exibir com plotly; senão, lista
try:
    import plotly.express as px
    import pandas as pd

    if not semana.empty:
        def _dt(row):
            d = row["__d"] or ini_sem
            hi = parse_hhmm(row.get("HoraInicio","")) or time(0,0)
            hf = parse_hhmm(row.get("HoraFim",""))
            end_dt = datetime.combine(d, hf) if hf else (datetime.combine(d, hi) + timedelta(minutes=50))
            return datetime.combine(d, hi), end_dt

        starts, ends = zip(*semana.apply(_dt, axis=1)) if not semana.empty else ([],[])
        semana["__start"] = list(starts); semana["__end"] = list(ends)
        semana["__day"] = semana["__d"].apply(lambda d: WEEKDAYS_PT[d.weekday()] if d else "-")
        fig = px.timeline(
            semana, x_start="__start", x_end="__end", y="__day", color="Nome",
            hover_data={"Data":True,"HoraInicio":True,"HoraFim":True,"Profissional":True,"Status":True,"Tipo":True}
        )
        fig.update_yaxes(categoryorder='array', categoryarray=WEEKDAYS_PT)
        fig.update_layout(height=420, showlegend=True, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem sessões nesta semana.")
except Exception:
    if semana.empty:
        st.info("Sem sessões nesta semana.")
    else:
        for i in range(7):
            d = ini_sem + timedelta(days=i)
            dd = semana[semana["__d"] == d].copy()
            if dd.empty: continue
            st.markdown(f"**{WEEKDAYS_PT[d.weekday()]} — {br_date(d)}**")
            dd = dd.sort_values("HoraInicio")
            cols = ["HoraInicio","HoraFim","Nome","Profissional","Tipo","Status"]
            cols = [c for c in cols if c in dd.columns]
            st.dataframe(dd[cols], use_container_width=True, hide_index=True)

st.divider()

# ================= abas =================
tab_pontual, tab_rec, tab_edit = st.tabs(["📝 Agendar pontual", "🔁 Agendar recorrente", "🛠️ Editar / Apagar"])

# ---------- Agendar pontual ----------
with tab_pontual:
    with st.form("nova_sessao_pontual"):
        nomes = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
        nome_sel = st.selectbox("Paciente", nomes)
        pid = df_pac.loc[df_pac["Nome"].astype(str).str.strip()==nome_sel, "PacienteID"].astype(str).iloc[0] if nome_sel else ""
        data_sel = st.date_input("Data", value=date.today(), key="pont_data")
        hi_txt = st.text_input("Hora início (HH:MM)", key="pont_hi")
        hf_txt = st.text_input("Hora fim (HH:MM)", key="pont_hf")
        prof = st.text_input("Profissional", "Terapeuta", key="pont_prof")
        status = st.selectbox("Status", ["Agendada","Realizada","Falta","Cancelada"], index=0, key="pont_status")
        tipo = st.selectbox("Tipo", ["Terapia","Avaliação","Retorno"], index=0, key="pont_tipo")
        objetivos = st.text_input("Objetivos trabalhados (resumo)", key="pont_obj")
        obs = st.text_area("Observações", key="pont_obs")
        anexos = st.text_input("AnexosURL (opcional)", key="pont_anexos")
        ok = st.form_submit_button("Salvar")

    if ok:
        if not pid: st.error("Selecione um paciente."); st.stop()
        hi = parse_hhmm(hi_txt); hf = parse_hhmm(hf_txt) if hf_txt.strip() else None
        if not hi: st.error("Informe **Hora início** em HH:MM."); st.stop()
        if hf and to_min(hf) <= to_min(hi): st.error("**Hora fim** > **Hora início**."); st.stop()

        data_str = br_date(data_sel)

        # trava duplicidade (mesmo paciente/dia e sobreposição)
        mesmo_dia = df_ses[(df_ses["PacienteID"].astype(str)==pid) & (df_ses["Data"].astype(str).str.strip()==data_str)]
        conflito = False
        for _, r in mesmo_dia.iterrows():
            e_hi = parse_hhmm(r.get("HoraInicio",""))
            e_hf = parse_hhmm(r.get("HoraFim","")) if str(r.get("HoraFim","")).strip() else None
            if str(r.get("Status","")).strip().lower()=="cancelada": continue
            if overlap(hi, hf, e_hi, e_hf): conflito=True; break
        if conflito:
            st.error("⚠️ Conflito de horário para este paciente nesse dia."); st.stop()

        sid = new_id("S")
        append_rows(ws, [{
            "SessaoID": sid, "PacienteID": pid, "Data": data_str,
            "HoraInicio": hi_txt.strip(), "HoraFim": hf_txt.strip(),
            "Profissional": prof.strip(), "Status": status.strip(), "Tipo": tipo.strip(),
            "ObjetivosTrabalhados": objetivos.strip(), "Observacoes": obs.strip(), "AnexosURL": anexos.strip()
        }], default_headers=SES_COLS)
        st.success(f"Sessão salva para **{nome_sel}** ({sid})")
        st.cache_data.clear(); st.rerun()

# ---------- Agendar recorrente ----------
with tab_rec:
    with st.form("nova_recorrencia"):
        nomes_r = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
        nome_r = st.selectbox("Paciente", nomes_r, key="rec_nome")
        pid_r = df_pac.loc[df_pac["Nome"].astype(str).str.strip()==nome_r, "PacienteID"].astype(str).iloc[0] if nome_r else ""
        ca, cb = st.columns([1,1])
        with ca:
            dias_semana = st.multiselect("Dia(s) da semana", options=list(range(7)), default=[1],
                                         format_func=lambda i: WEEKDAYS_PT[i])
            hi_r = st.text_input("Hora início (HH:MM)", "15:00", key="rec_hi")
            hf_r = st.text_input("Hora fim (HH:MM)", "15:50", key="rec_hf")
        with cb:
            data_ini = st.date_input("Início (primeira semana)", value=date.today(), key="rec_ini")
            semanas = st.number_input("Repetir por (semanas)", min_value=1, max_value=52, value=12, step=1, key="rec_rep")
            prof_r = st.text_input("Profissional", "Terapeuta", key="rec_prof")
        status_r = st.selectbox("Status padrão", ["Agendada","Realizada","Falta","Cancelada"], index=0, key="rec_status")
        tipo_r   = st.selectbox("Tipo", ["Terapia","Avaliação","Retorno"], index=0, key="rec_tipo")
        obs_r    = st.text_input("Observações (aplicadas a todas)", "Recorrente", key="rec_obs")
        ok_rec = st.form_submit_button("Criar sessões recorrentes")

    if ok_rec:
        if not pid_r: st.error("Selecione um paciente."); st.stop()
        hi = parse_hhmm(hi_r); hf = parse_hhmm(hf_r) if hf_r.strip() else None
        if not hi: st.error("Hora início inválida."); st.stop()
        if hf and to_min(hf) <= to_min(hi): st.error("**Hora fim** > **Hora início**."); st.stop()
        if not dias_semana: st.error("Escolha ao menos um dia da semana."); st.stop()

        start_week, _ = week_bounds(data_ini)
        criadas, puladas = [], []
        for w in range(semanas):
            base = start_week + timedelta(weeks=w)
            for dow in sorted(dias_semana):
                d = base + timedelta(days=dow)
                data_str = br_date(d)
                mesmo_dia = df_ses[(df_ses["PacienteID"].astype(str)==pid_r) & (df_ses["Data"].astype(str).str.strip()==data_str)]
                tem_conf = False
                for _, r in mesmo_dia.iterrows():
                    e_hi = parse_hhmm(r.get("HoraInicio",""))
                    e_hf = parse_hhmm(r.get("HoraFim","")) if str(r.get("HoraFim","")).strip() else None
                    if str(r.get("Status","")).strip().lower()=="cancelada": continue
                    if overlap(hi, hf, e_hi, e_hf): tem_conf=True; break
                if tem_conf: puladas.append(data_str); continue
                criadas.append({
                    "SessaoID": new_id("S"), "PacienteID": pid_r, "Data": data_str,
                    "HoraInicio": hi_r.strip(), "HoraFim": hf_r.strip(),
                    "Profissional": prof_r.strip(), "Status": status_r.strip(), "Tipo": tipo_r.strip(),
                    "ObjetivosTrabalhados": "", "Observacoes": obs_r.strip(), "AnexosURL": ""
                })
        if not criadas:
            st.warning("Nenhuma sessão criada (todas conflitaram?).")
            if puladas: st.caption(f"Puladas: {len(puladas)}")
            st.stop()
        append_rows(ws, criadas, default_headers=SES_COLS)
        st.success(f"✅ Criadas {len(criadas)} sessões recorrentes para **{nome_r}**.")
        if puladas: st.info(f"⚠️ {len(puladas)} data(s) ignoradas por conflito.")
        st.cache_data.clear(); st.rerun()

# ---------- Editar / Apagar ----------
with tab_edit:
    st.markdown("### 🛠️ Editar ou Apagar sessão")
    colf1, colf2 = st.columns(2)
    with colf1:
        de = st.date_input("De", value=ini_sem)
    with colf2:
        ate = st.date_input("Até", value=fim_sem)

    faixa = df_ses[(df_ses["__d"] >= de) & (df_ses["__d"] <= ate)].merge(
        df_pac[["PacienteID","Nome"]], on="PacienteID", how="left"
    ).copy()

    if faixa.empty:
        st.info("Nenhuma sessão no período selecionado.")
    else:
        faixa = faixa.sort_values(["Data","HoraInicio","Nome"])

        def _label(r):
            return f"{r['Data']} • {r.get('HoraInicio','--')}–{r.get('HoraFim','--')} • {r.get('Nome','-')} • {r.get('Profissional','') or 'Prof.'} • {r.get('Status','') or ''}"

        options = { _label(r): (r["SessaoID"], int(r["__rownum"])) for _, r in faixa.iterrows() }
        escolha = st.selectbox("Escolha a sessão", list(options.keys()))
        sid_sel, rownum = options.get(escolha, (None, None))

        if sid_sel and rownum:
            # linha original
            linha = df_ses[df_ses["SessaoID"] == sid_sel].head(1).iloc[0]

            st.markdown(f"**Sessão:** `{sid_sel}`  •  Linha: {rownum}")

            # ------- FORM DE EDIÇÃO -------
            with st.form("edit_form"):
                data_e = st.date_input("Data", value=parse_br_date(linha["Data"]) or date.today())
                hi_e = st.text_input("Hora início (HH:MM)", str(linha.get("HoraInicio","") or ""))
                hf_e = st.text_input("Hora fim (HH:MM)", str(linha.get("HoraFim","") or ""))
                prof_e = st.text_input("Profissional", str(linha.get("Profissional","") or "Terapeuta"))

                status_opts = ["Agendada","Realizada","Falta","Cancelada"]
                try:
                    st_idx = status_opts.index(str(linha.get("Status","Agendada")))
                except ValueError:
                    st_idx = 0
                status_e = st.selectbox("Status", status_opts, index=st_idx)

                tipo_opts = ["Terapia","Avaliação","Retorno"]
                try:
                    tp_idx = tipo_opts.index(str(linha.get("Tipo","Terapia")))
                except ValueError:
                    tp_idx = 0
                tipo_e = st.selectbox("Tipo", tipo_opts, index=tp_idx)

                objetivos_e = st.text_input("Objetivos trabalhados", str(linha.get("ObjetivosTrabalhados","") or ""))
                obs_e = st.text_area("Observações", str(linha.get("Observacoes","") or ""))
                anexos_e = st.text_input("AnexosURL", str(linha.get("AnexosURL","") or ""))

                c_upd, c_del = st.columns(2)
                salvar = c_upd.form_submit_button("💾 Salvar alterações", use_container_width=True)
                pedir_apagar = c_del.form_submit_button("🗑️ Apagar sessão", use_container_width=True)

            if salvar:
                hi_v = parse_hhmm(hi_e)
                hf_v = parse_hhmm(hf_e) if hf_e.strip() else None
                if not hi_v:
                    st.error("Hora início inválida.")
                    st.stop()
                if hf_v and to_min(hf_v) <= to_min(hi_v):
                    st.error("**Hora fim** deve ser maior que **Hora início**.")
                    st.stop()

                updates = [
                    ("Data", br_date(data_e)),
                    ("HoraInicio", hi_e.strip()),
                    ("HoraFim", hf_e.strip()),
                    ("Profissional", prof_e.strip()),
                    ("Status", status_e.strip()),
                    ("Tipo", tipo_e.strip()),
                    ("ObjetivosTrabalhados", objetivos_e.strip()),
                    ("Observacoes", obs_e.strip()),
                    ("AnexosURL", anexos_e.strip()),
                ]
                for col, val in updates:
                    ci = col_idx.get(col)
                    if ci:
                        ws.update_cell(rownum, ci, val)

                st.success("Sessão atualizada com sucesso.")
                st.cache_data.clear()
                st.rerun()

            # ------- ETAPA 1: marcar exclusão pendente -------
            if pedir_apagar:
                st.session_state["__pending_delete"] = {
                    "sid": sid_sel,
                    "rownum": int(rownum),
                    "desc": escolha,
                }
                st.rerun()

# ------- ETAPA 2: confirmar fora do form (não reseta) -------
pend = st.session_state.get("__pending_delete")
if pend:
    st.error("⚠️ Confirma remover permanentemente a sessão abaixo?")
    st.write(pend["desc"])
    col_c, col_x = st.columns(2)
    if col_c.button("✅ Confirmar exclusão", key="confirm_delete_btn", use_container_width=True):
        try:
            ws.delete_rows(int(pend["rownum"]))
            st.success("Sessão apagada.")
        except Exception as e:
            st.error(f"Erro ao apagar: {e}")
        finally:
            st.session_state.pop("__pending_delete", None)
            st.cache_data.clear()
            st.rerun()
    if col_x.button("❌ Cancelar", key="cancel_delete_btn", use_container_width=True):
        st.session_state.pop("__pending_delete", None)
        st.info("Exclusão cancelada.")
        st.rerun()
