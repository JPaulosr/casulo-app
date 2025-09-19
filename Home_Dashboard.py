# Home_Dashboard.py
# 🦋 Casulo | Dashboard

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, time
from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Dashboard", page_icon="🦋", layout="wide")
st.title("🦋 Casulo | Dashboard")

# ---------- CSS leve p/ chips e cards ----------
st.markdown("""
<style>
.badge {display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;}
.st-status-agendada  {background:#f1f5f9;color:#0f172a;}
.st-status-confirmada{background:#dcfce7;color:#166534;}
.st-status-realizada {background:#e0e7ff;color:#3730a3;}
.st-status-falta     {background:#fee2e2;color:#991b1b;}
.st-status-cancelada {background:#f5f5f5;color:#525252;text-decoration:line-through;}
.small {font-size:12px;color:#475569}
.item {padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:8px;}
.item:hover {background:#fafafa}
.hdim {opacity:0.75}
</style>
""", unsafe_allow_html=True)

# ---------- helpers ----------
def to_date(s):
    if s is None: return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try: return datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

def to_float(x) -> float:
    try:
        s = str(x).strip().replace("R$", "").replace(" ", "")
        # se vier "1.234,56"
        if s.count(",")==1 and s.count(".")>=1:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def brl(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

def parse_hhmm(txt: str):
    try:
        return datetime.strptime(str(txt).strip(), "%H:%M").time()
    except Exception:
        return None

def week_bounds(anchor: date):
    start = anchor - timedelta(days=anchor.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end

WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# ---------- conexão & colunas ----------
ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim",
            "Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido",
            "TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes",   SES_COLS)
df_pag, _ = read_ws(ss, "Pagamentos",PAG_COLS)

# ---------- normalizações ----------
df_pac = df_pac.copy()
df_ses = df_ses.copy()
df_pag = df_pag.copy()

df_pac["__status_norm"] = df_pac.get("Status","").astype(str).str.strip().str.lower() if not df_pac.empty else []
df_ses["__dt"] = df_ses.get("Data","").apply(to_date) if "Data" in df_ses else None
df_ses["__hi"] = df_ses.get("HoraInicio","").apply(parse_hhmm) if "HoraInicio" in df_ses else None
df_ses["__hf"] = df_ses.get("HoraFim","").apply(parse_hhmm) if "HoraFim" in df_ses else None

df_pag["__dt"] = df_pag.get("Data","").apply(to_date) if "Data" in df_pag else None
df_pag["__bruto"]   = df_pag.get("Bruto",0).apply(to_float)
df_pag["__liquido"] = df_pag.get("Liquido",0).apply(to_float)

# ---------- datas base ----------
hoje = date.today()
ini_sem, fim_sem = week_bounds(hoje)
mes_ini = hoje.replace(day=1)

# ---------- KPIs ----------
ativos = int((df_pac["__status_norm"] == "ativo").sum()) if not df_pac.empty else 0

semana_atual   = df_ses[(df_ses["__dt"] >= ini_sem) & (df_ses["__dt"] <= fim_sem)] if "__dt" in df_ses else df_ses.iloc[0:0]
semana_passada = df_ses[(df_ses["__dt"] >= ini_sem - timedelta(days=7)) & (df_ses["__dt"] <= fim_sem - timedelta(days=7))] if "__dt" in df_ses else df_ses.iloc[0:0]
qtd_semana   = int(len(semana_atual))
delta_semana = qtd_semana - int(len(semana_passada))

pag_mes = df_pag[(df_pag["__dt"] >= mes_ini) & (df_pag["__dt"] <= hoje)]
fat_mes_bruto   = float(pag_mes["__bruto"].sum())
fat_mes_liquido = float(pag_mes["__liquido"].sum())
qtd_pags_mes    = int(len(pag_mes))

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Pacientes ativos", ativos)
c2.metric("🗓️ Sessões nesta semana", qtd_semana, delta_semana if delta_semana else None)
c3.metric("💰 Faturamento no mês (líquido)", brl(fat_mes_liquido))
c4.metric("🧾 Pagamentos no mês", qtd_pags_mes)

st.divider()

# ---------- Navegação semanal ----------
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0
col_prev, col_today, col_next = st.columns(3)
if col_prev.button("← Semana anterior", use_container_width=True):
    st.session_state.week_offset -= 1; st.rerun()
if col_today.button("Hoje", use_container_width=True):
    st.session_state.week_offset = 0; st.rerun()
if col_next.button("Próxima semana →", use_container_width=True):
    st.session_state.week_offset += 1; st.rerun()

anchor = hoje + timedelta(weeks=st.session_state.week_offset)
sem_ini, sem_fim = week_bounds(anchor)
st.subheader(f"🗓️ Agenda da semana ({sem_ini.strftime('%d/%m')} → {sem_fim.strftime('%d/%m')})")

# filtro por profissional/status (leves)
colF1, colF2 = st.columns([1,1])
with colF1:
    prof_f = st.text_input("Filtrar por profissional (opcional)", "")
with colF2:
    status_f = st.multiselect("Status", ["Agendada","Confirmada","Realizada","Falta","Cancelada"], default=["Agendada","Confirmada","Realizada"])

semana = df_ses[(df_ses["__dt"] >= sem_ini) & (df_ses["__dt"] <= sem_fim)].copy()
if prof_f.strip():
    semana = semana[semana.get("Profissional","").astype(str).str.contains(prof_f.strip(), case=False, na=False)]
if status_f:
    semana = semana[semana.get("Status","").astype(str).isin(status_f)]

# junta nome
if not semana.empty and "PacienteID" in semana and "PacienteID" in df_pac:
    semana = semana.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")

# calendário com Plotly (fallback tabela)
try:
    import plotly.express as px

    if not semana.empty:
        def _dt(row):
            d = row["__dt"] or sem_ini
            hi = parse_hhmm(row.get("HoraInicio","")) or time(0,0)
            hf = parse_hhmm(row.get("HoraFim",""))
            end_dt = datetime.combine(d, hf) if hf else (datetime.combine(d, hi) + timedelta(minutes=50))
            return datetime.combine(d, hi), end_dt

        starts, ends = zip(*semana.apply(_dt, axis=1)) if not semana.empty else ([],[])
        semana["__start"] = list(starts); semana["__end"] = list(ends)
        semana["__day"] = semana["__dt"].apply(lambda d: WEEKDAYS_PT[d.weekday()] if d else "-")
        fig = px.timeline(
            semana, x_start="__start", x_end="__end", y="__day", color="Nome",
            hover_data={"Data":True,"HoraInicio":True,"HoraFim":True,"Profissional":True,"Status":True,"Tipo":True}
        )
        fig.update_yaxes(categoryorder='array', categoryarray=WEEKDAYS_PT)
        fig.update_layout(height=420, showlegend=True, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem sessões nesta semana com os filtros atuais.")
except Exception:
    # fallback por dia
    if semana.empty:
        st.info("Sem sessões nesta semana com os filtros atuais.")
    else:
        for i in range(7):
            d = sem_ini + timedelta(days=i)
            dd = semana[semana["__dt"] == d].copy()
            if dd.empty: continue
            st.markdown(f"**{WEEKDAYS_PT[d.weekday()]} — {d.strftime('%d/%m/%Y')}**")
            dd = dd.sort_values(["HoraInicio","Nome"])
            cols = ["HoraInicio","HoraFim","Nome","Profissional","Tipo","Status"]
            cols = [c for c in cols if c in dd.columns]
            st.dataframe(dd[cols], use_container_width=True, hide_index=True)

st.divider()

# ---------- Hoje & próximos 7 dias (lista bonita) ----------
st.subheader("📅 Hoje & próximos 7 dias")
prox = df_ses[(df_ses["__dt"] >= hoje) & (df_ses["__dt"] <= hoje + timedelta(days=7))].copy()
if not prox.empty and "PacienteID" in prox and "PacienteID" in df_pac:
    prox = prox.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
if prox.empty:
    st.info("Sem sessões agendadas nos próximos 7 dias.")
else:
    prox["__ord_h"] = prox["__hi"].apply(lambda t: (t.hour*60 + t.minute) if t else 9999)
    prox = prox.sort_values(["__dt","__ord_h","Nome"])
    # render grupo por dia
    for d, bloco in prox.groupby("__dt"):
        st.markdown(f"**{d.strftime('%d/%m/%Y')}**")
        for _, r in bloco.iterrows():
            nome = str(r.get("Nome","-"))
            hi = str(r.get("HoraInicio","--"))
            hf = str(r.get("HoraFim","") or "")
            prof = str(r.get("Profissional","") or "")
            status = str(r.get("Status","Agendada")).strip().lower()
            cls = {
                "agendada":"st-status-agendada",
                "confirmada":"st-status-confirmada",
                "realizada":"st-status-realizada",
                "falta":"st-status-falta",
                "cancelada":"st-status-cancelada"
            }.get(status, "st-status-agendada")
            st.markdown(
                f"<div class='item'><div><b>{hi}{('–'+hf) if hf else ''}</b> · {nome} "
                f"<span class='badge {cls}'>{r.get('Status','Agendada')}</span></div>"
                f"<div class='small hdim'>{r.get('Tipo','Terapia') or 'Terapia'} · {prof}</div></div>",
                unsafe_allow_html=True
            )

st.divider()

# ---------- Gráficos simples de receita ----------
st.subheader("💵 Receita do mês")
if pag_mes.empty:
    st.info("Sem pagamentos neste mês.")
else:
    # série diária (líquido)
    daily = (pag_mes.groupby("__dt")["__liquido"].sum()
             .reindex([mes_ini + timedelta(days=i) for i in range((hoje-mes_ini).days+1)], fill_value=0.0))
    df_line = pd.DataFrame({"Data": daily.index, "Líquido": daily.values}).set_index("Data")
    st.line_chart(df_line, use_container_width=True)

    # por forma (líquido)
    por_forma = pag_mes.groupby("Forma")["__liquido"].sum().sort_values(ascending=False)
    if not por_forma.empty:
        st.bar_chart(por_forma, use_container_width=True)

st.divider()

# ---------- Pacientes (resumo) ----------
st.subheader("👨‍👩‍👧 Pacientes (resumo)")
if not df_pac.empty:
    cols_pac = ["PacienteID","Nome","Responsavel","Telefone","Status","Prioridade"]
    cols_pac = [c for c in cols_pac if c in df_pac.columns]
    st.dataframe(df_pac[cols_pac], use_container_width=True, hide_index=True)
else:
    st.info("Nenhum paciente cadastrado ainda.")
