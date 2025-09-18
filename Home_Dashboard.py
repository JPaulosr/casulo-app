# Home_Dashboard.py
# 🦋 Casulo | Dashboard

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Dashboard", page_icon="🦋", layout="wide")
st.title("🦋 Casulo | Dashboard")

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
        s = s.replace(".", "").replace(",", ".") if s.count(",")==1 and s.count(".")>1 else s
        return float(s.replace(",", "."))
    except Exception:
        return 0.0

def brl(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

# ---------- conexão ----------
ss = connect()

# ---------- colunas ----------
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim",
            "Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido",
            "TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

# ---------- leitura ----------
df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes",   SES_COLS)
df_pag, _ = read_ws(ss, "Pagamentos",PAG_COLS)

# maps id<->nome
id2name = {}
if not df_pac.empty:
    id2name = {str(r["PacienteID"]): str(r["Nome"]) for _, r in df_pac.iterrows()}

# normalizações
df_pac["__status_norm"] = df_pac.get("Status","").astype(str).str.strip().str.lower() if not df_pac.empty else []
df_ses["__dt"] = df_ses.get("Data","").apply(to_date)
df_pag["__dt"] = df_pag.get("Data","").apply(to_date)
df_pag["__bruto"]   = df_pag.get("Bruto",0).apply(to_float)
df_pag["__liquido"] = df_pag.get("Liquido",0).apply(to_float)

hoje = date.today()
ini_sem = hoje - timedelta(days=hoje.weekday())
fim_sem = ini_sem + timedelta(days=6)

# ---------- métricas ----------
ativos = int((df_pac["__status_norm"] == "ativo").sum()) if not df_pac.empty else 0
semana_atual   = df_ses[(df_ses["__dt"] >= ini_sem) & (df_ses["__dt"] <= fim_sem)]
semana_passada = df_ses[(df_ses["__dt"] >= ini_sem - timedelta(days=7)) & (df_ses["__dt"] <= fim_sem - timedelta(days=7))]
qtd_semana   = int(len(semana_atual))
delta_semana = qtd_semana - int(len(semana_passada))

mes_ini = hoje.replace(day=1)
fat_mes = float(df_pag[(df_pag["__dt"] >= mes_ini) & (df_pag["__dt"] <= hoje)]["__bruto"].sum())
qtd_pags_mes = int(len(df_pag[(df_pag["__dt"] >= mes_ini) & (df_pag["__dt"] <= hoje)]))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pacientes ativos", ativos)
c2.metric("Sessões nesta semana", qtd_semana, delta_semana if delta_semana else None)
c3.metric("Faturamento no mês (bruto)", brl(fat_mes))
c4.metric("Pagamentos no mês", qtd_pags_mes)

st.divider()

# ---------- Próximas sessões (7 dias) ----------
st.subheader("📅 Próximas sessões (7 dias)")
proximos = df_ses[(df_ses["__dt"] >= hoje) & (df_ses["__dt"] <= hoje + timedelta(days=7))].copy()
if not proximos.empty:
    # junta nome
    proximos = proximos.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
    try:
        proximos["__hora_ord"] = pd.to_datetime(proximos["HoraInicio"], format="%H:%M", errors="coerce")
    except Exception:
        proximos["__hora_ord"] = None
    proximos = proximos.sort_values(["__dt","__hora_ord"], ascending=[True, True])
    cols_show = ["Data","HoraInicio","Nome","Profissional","Status","Tipo"]
    cols_show = [c for c in cols_show if c in proximos.columns]
    st.dataframe(proximos[cols_show], use_container_width=True, hide_index=True)
else:
    st.info("Sem sessões agendadas nos próximos 7 dias.")

st.divider()

# ---------- Últimos pagamentos ----------
st.subheader("💳 Últimos pagamentos")
ult = df_pag.dropna(subset=["__dt"]).copy()
if not ult.empty:
    ult = ult.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
    ult = ult.sort_values("__dt", ascending=False).head(10)
    if "Bruto" in ult.columns:   ult["Bruto"]   = ult["__bruto"].apply(brl)
    if "Liquido" in ult.columns: ult["Liquido"] = ult["__liquido"].apply(brl)
    cols_pay = ["Data","Nome","Forma","Bruto","Liquido","Referencia","Obs"]
    cols_pay = [c for c in cols_pay if c in ult.columns]
    st.dataframe(ult[cols_pay], use_container_width=True, hide_index=True)
else:
    st.info("Ainda não há pagamentos registrados.")

st.divider()
st.subheader("👨‍👩‍👧 Pacientes (resumo)")
if not df_pac.empty:
    cols_pac = ["PacienteID","Nome","Responsavel","Telefone","Status","Prioridade"]
    cols_pac = [c for c in cols_pac if c in df_pac.columns]
    st.dataframe(df_pac[cols_pac], use_container_width=True, hide_index=True)
else:
    st.info("Nenhum paciente cadastrado ainda.")

with st.expander("🔧 Diagnóstico técnico"):
    try:
        st.write("Abas:", [w.title for w in ss.worksheets()])
    except Exception as e:
        st.warning(f"Não consegui listar as abas: {e}")
    if st.button("Atualizar dados (limpar cache)"):
        st.cache_data.clear()
        st.rerun()
