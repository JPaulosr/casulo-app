# Home_Dashboard.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Dashboard", page_icon="🦋", layout="wide")
st.title("🦋 Casulo | Dashboard")

ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email","Diagnostico",
            "Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes", SES_COLS)
df_pag, _ = read_ws(ss, "Pagamentos", PAG_COLS)

ativos = (df_pac.get("Status","").astype(str).str.lower() == "ativo").sum()
st.metric("Pacientes ativos", int(ativos))

# sessões semana
def to_date(s): 
    try: return datetime.strptime(str(s), "%d/%m/%Y").date()
    except: return None

df_ses["__dt"] = df_ses["Data"].apply(to_date)
hoje = date.today()
ini = hoje - timedelta(days=hoje.weekday())  # segunda
fim = ini + timedelta(days=6)
semana = df_ses[(df_ses["__dt"]>=ini) & (df_ses["__dt"]<=fim)]
st.metric("Sessões nesta semana", int(len(semana)))

# faturamento mês (bruto)
def to_float(x):
    try: return float(str(x).replace(",", "."))
    except: return 0.0

df_pag["__dt"] = df_pag["Data"].apply(to_date)
mes_ini = hoje.replace(day=1)
mes = df_pag[(df_pag["__dt"]>=mes_ini) & (df_pag["__dt"]<=hoje)]
fat_mes = mes["Bruto"].apply(to_float).sum()
st.metric("Faturamento no mês (bruto)", f"R$ {fat_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))

st.divider()
st.subheader("Próximas sessões (7 dias)")
prox = df_ses[(df_ses["__dt"]>=hoje) & (df_ses["__dt"]<=hoje+timedelta(days=7))].copy()
cols = ["Data","HoraInicio","PacienteID","Profissional","Status","Tipo"]
st.dataframe(prox[cols], use_container_width=True, hide_index=True)
