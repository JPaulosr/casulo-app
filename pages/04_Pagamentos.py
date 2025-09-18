# pages/04_Pagamentos.py
import streamlit as st
from datetime import date
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Pagamentos", page_icon="💳", layout="wide")
st.title("💳 Pagamentos")

ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email","Diagnostico",
            "Convenio","Status","Prioridade","FotoURL","Observacoes"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_pag, ws = read_ws(ss, "Pagamentos", PAG_COLS)

st.subheader("Em aberto (visão simples)")
# como não fizemos faturas, considere “em aberto” via regras futuras; aqui listamos históricos
st.dataframe(df_pag[["Data","PacienteID","Forma","Bruto","Liquido","Referencia","Obs"]], use_container_width=True, hide_index=True)

st.subheader("Registrar pagamento")
with st.form("novo_pagamento"):
    pid = st.selectbox("Paciente", df_pac["PacienteID"].astype(str).tolist())
    data = st.date_input("Data", value=date.today())
    forma = st.selectbox("Forma", ["Pix","Dinheiro","Cartão","Transferência"], index=0)
    bruto = st.number_input("Bruto", min_value=0.0, step=1.0, format="%.2f", value=0.00)
    liquido = st.number_input("Líquido (se cartão, coloque já com taxa)", min_value=0.0, step=1.0, format="%.2f", value=0.00)
    ref = st.text_input("Referência (ex.: 09/2025)", "")
    obs = st.text_input("Obs.", "")
    taxa_val = max(0.0, bruto - liquido) if bruto and liquido else 0.0
    taxa_pct = (taxa_val/bruto*100.0) if bruto>0 else 0.0
    st.caption(f"Taxa estimada: R$ {taxa_val:.2f} ({taxa_pct:.2f}%)")
    ok = st.form_submit_button("Salvar")
    if ok:
        pid_pg = new_id("PG")
        append_rows(ws, [{
            "PagamentoID": pid_pg, "PacienteID": pid, "Data": data.strftime("%d/%m/%Y"),
            "Forma": forma, "Bruto": bruto, "Liquido": liquido,
            "TaxaValor": round(taxa_val,2), "TaxaPct": round(taxa_pct,2),
            "Referencia": ref, "Obs": obs, "ReciboURL": ""
        }], default_headers=PAG_COLS)
        st.success(f"Pagamento registrado ({pid_pg})")
        st.cache_data.clear()
