# pages/04_Pagamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Pagamentos", page_icon="💳", layout="wide")
st.title("💳 Pagamentos")

# ---------------- helpers ----------------
def _fmt_brl(v) -> str:
    try:
        x = float(v)
    except Exception:
        return "R$ 0,00"
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _fmt_pct(p) -> str:
    try:
        x = float(p)
    except Exception:
        return "0,00%"
    return f"{x:.2f}%"

def _parse_dt_br(s: str):
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None

# ---------------- dados ----------------
ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes", PAC_COLS)
df_pag, ws = read_ws(ss, "Pagamentos", PAG_COLS)

# índices de coluna p/ update
headers = ws.row_values(1)
col_idx = {h: i+1 for i, h in enumerate(headers)}  # 1-based

# prepara df
df_pag = df_pag.copy()
df_pag["__rownum"] = df_pag.index + 2  # header na linha 1
df_pag["__d"] = df_pag["Data"].apply(_parse_dt_br)

# ===================== TABS =====================
tab_hist, tab_cad, tab_edit = st.tabs(["📚 Histórico & Relatórios", "📝 Registrar", "🛠️ Editar / Apagar"])

# ============================================================
# 📚 HISTÓRICO
# ============================================================
with tab_hist:
    st.subheader("Histórico & Relatórios")

    colf1, colf2, colf3, colf4 = st.columns([1,1,1,1])
    with colf1:
        de = st.date_input("De", value=(date.today().replace(day=1)))
    with colf2:
        ate = st.date_input("Até", value=date.today())
    with colf3:
        filtro_nome = st.text_input("Paciente (contém)", "")
    with colf4:
        forma_sel = st.selectbox("Forma", ["(todas)","Pix","Dinheiro","Cartão","Transferência"], index=0)

    ref_txt = st.text_input("Referência (contém, ex.: 09/2025)", "")

    vis = df_pag.copy()
    if de:
        vis = vis[vis["__d"] >= de]
    if ate:
        vis = vis[vis["__d"] <= ate]
    if filtro_nome.strip():
        # junta nome
        vis = vis.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
        vis = vis[vis["Nome"].astype(str).str.contains(filtro_nome.strip(), case=False, na=False)]
    else:
        vis = vis.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
    if forma_sel != "(todas)":
        vis = vis[vis["Forma"].astype(str) == forma_sel]
    if ref_txt.strip():
        vis = vis[vis["Referencia"].astype(str).str.contains(ref_txt.strip(), case=False, na=False)]

    # números
    for c in ["Bruto","Liquido","TaxaValor","TaxaPct"]:
        vis[c] = pd.to_numeric(vis[c], errors="coerce").fillna(0.0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pagamentos", f"{len(vis)}")
    c2.metric("Total bruto", _fmt_brl(vis["Bruto"].sum()))
    c3.metric("Total líquido", _fmt_brl(vis["Liquido"].sum()))
    c4.metric("Taxas", _fmt_brl(vis["TaxaValor"].sum()))

    # tabela
    cols_show = ["Data","Nome","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","PagamentoID"]
    st.dataframe(
        vis[cols_show].sort_values("Data", ascending=False),
        use_container_width=True, hide_index=True
    )

    # agrupados
    st.markdown("---")
    st.markdown("#### 📊 Resumos")
    if not vis.empty:
        tmp = vis.copy()
        # mês/ano da data
        tmp["MesRef"] = tmp["__d"].apply(lambda d: d.strftime("%Y-%m") if d else "")
        grp_mes = (tmp.groupby("MesRef", as_index=False)[["Bruto","Liquido","TaxaValor"]].sum()
                      .sort_values("MesRef", ascending=False))
        grp_forma = (tmp.groupby("Forma", as_index=False)[["Bruto","Liquido","TaxaValor"]].sum()
                       .sort_values("Liquido", ascending=False))
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("Por mês (data do pagamento)")
            st.dataframe(grp_mes, use_container_width=True, hide_index=True)
        with col_b:
            st.write("Por forma")
            st.dataframe(grp_forma, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados no filtro para resumir.")

    # export
    st.markdown("---")
    st.download_button(
        "⬇️ Exportar CSV (filtro aplicado)",
        data=vis[cols_show].to_csv(index=False).encode("utf-8-sig"),
        file_name="pagamentos_filtrados.csv"
    )

# ============================================================
# 📝 REGISTRAR
# ============================================================
with tab_cad:
    st.subheader("Registrar pagamento")

    nomes = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
    with st.form("novo_pagamento"):
        col1, col2 = st.columns([2,1])
        with col1:
            nome_sel = st.selectbox("Paciente", nomes)
        with col2:
            data_pg = st.date_input("Data", value=date.today())

        pid = ""
        if nome_sel:
            pid = df_pac.loc[df_pac["Nome"].astype(str).str.strip() == nome_sel, "PacienteID"].astype(str).iloc[0]

        col3, col4, col5 = st.columns([1,1,1])
        with col3:
            forma = st.selectbox("Forma", ["Pix","Dinheiro","Cartão","Transferência"], index=0)
        with col4:
            bruto = st.number_input("Bruto", min_value=0.0, step=1.0, format="%.2f", value=0.00)
        with col5:
            usar_ref_mes = st.checkbox("Usar mês/ano da data na referência", value=True)

        # Cartão: escolher modo de cálculo
        liquido = 0.0
        taxa_val = 0.0
        taxa_pct = 0.0

        if forma == "Cartão":
            modo = st.radio("Como informar a taxa do cartão?", ["Informar líquido", "Informar taxa (%)"], horizontal=True)
            if modo == "Informar líquido":
                liquido = st.number_input("Líquido (já descontada a taxa)", min_value=0.0, step=1.0, format="%.2f", value=0.00)
                taxa_val = max(0.0, float(bruto) - float(liquido))
                taxa_pct = (taxa_val/float(bruto)*100.0) if bruto>0 else 0.0
            else:
                taxa_pct = st.number_input("Taxa (%)", min_value=0.0, step=0.1, format="%.2f", value=0.00)
                taxa_val = float(bruto) * float(taxa_pct)/100.0
                liquido = max(0.0, float(bruto) - taxa_val)
        else:
            liquido = float(bruto)
            taxa_val = 0.0
            taxa_pct = 0.0
            st.caption("Para Pix/Dinheiro/Transferência o líquido é igual ao bruto (sem taxas).")

        col6, col7 = st.columns([1,2])
        with col6:
            ref = (data_pg.strftime("%m/%Y") if usar_ref_mes else st.text_input("Referência", ""))
        with col7:
            obs = st.text_input("Obs.", "")

        st.info(f"💡 Taxa: {_fmt_brl(taxa_val)} ({_fmt_pct(taxa_pct)}) • Líquido: {_fmt_brl(liquido)}")

        salvar = st.form_submit_button("Salvar")

    if salvar:
        if not pid:
            st.error("Selecione um paciente.")
            st.stop()
        if forma == "Cartão" and (float(bruto) < float(liquido)):
            st.error("Para cartão, o **líquido** não pode ser maior que o **bruto**.")
            st.stop()

        pid_pg = new_id("PG")
        append_rows(ws, [{
            "PagamentoID": pid_pg,
            "PacienteID": pid,
            "Data": data_pg.strftime("%d/%m/%Y"),
            "Forma": forma,
            "Bruto": float(bruto),
            "Liquido": float(liquido),
            "TaxaValor": round(float(taxa_val), 2),
            "TaxaPct": round(float(taxa_pct), 2),
            "Referencia": ref,
            "Obs": obs,
            "ReciboURL": ""
        }], default_headers=PAG_COLS)

        st.success(f"Pagamento registrado para **{nome_sel}** ({pid_pg})")
        st.cache_data.clear()
        st.rerun()

# ============================================================
# 🛠️ EDITAR / APAGAR
# ============================================================
with tab_edit:
    st.subheader("Editar / Apagar pagamento")

    if df_pag.empty:
        st.info("Ainda não há pagamentos.")
        st.stop()

    # filtros listagem
    colE1, colE2 = st.columns(2)
    with colE1:
        de_e = st.date_input("De", value=(date.today().replace(day=1)), key="ed_de")
    with colE2:
        ate_e = st.date_input("Até", value=date.today(), key="ed_ate")
    nome_f = st.text_input("Paciente (contém)", "", key="ed_nome")
    forma_f = st.selectbox("Forma", ["(todas)","Pix","Dinheiro","Cartão","Transferência"], index=0, key="ed_forma")

    lista = df_pag.copy()
    if de_e:  lista = lista[lista["__d"] >= de_e]
    if ate_e: lista = lista[lista["__d"] <= ate_e]
    lista = lista.merge(df_pac[["PacienteID","Nome"]], on="PacienteID", how="left")
    if nome_f.strip():
        lista = lista[lista["Nome"].astype(str).str.contains(nome_f.strip(), case=False, na=False)]
    if forma_f != "(todas)":
        lista = lista[lista["Forma"].astype(str) == forma_f]

    if lista.empty:
        st.info("Nenhum pagamento no filtro.")
    else:
        lista = lista.sort_values(["Data","Nome"], ascending=[False, True])

        def _label(r):
            return f"{r['Data']} • {r['Nome']} • {r['Forma']} • Bruto {_fmt_brl(r['Bruto'])} • ({r['PagamentoID']})"

        options = { _label(r): (r["PagamentoID"], int(r["__rownum"])) for _, r in lista.iterrows() }
        escolha = st.selectbox("Escolha o pagamento", list(options.keys()))
        pid_sel, rownum = options.get(escolha, (None, None))

        if pid_sel and rownum:
            linha = df_pag[df_pag["PagamentoID"] == pid_sel].head(1).merge(
                df_pac[["PacienteID","Nome"]], on="PacienteID", how="left"
            ).iloc[0]

            st.markdown(f"**Pagamento:** `{pid_sel}`  •  Linha: {rownum}")
            with st.form("edit_pag"):
                # campos
                nome_atual = str(linha.get("Nome",""))
                # trocar paciente (opcional)
                nomes_all = sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
                nome_new = st.selectbox("Paciente", nomes_all, index=nomes_all.index(nome_atual) if nome_atual in nomes_all else 0, key="ed_nome_sel")
                pac_id_new = df_pac.loc[df_pac["Nome"].astype(str).str.strip()==nome_new, "PacienteID"].astype(str).iloc[0]

                data_e = st.date_input("Data", value=_parse_dt_br(linha["Data"]) or date.today(), key="ed_data")
                forma_e = st.selectbox("Forma", ["Pix","Dinheiro","Cartão","Transferência"], index=["Pix","Dinheiro","Cartão","Transferência"].index(str(linha["Forma"]) if str(linha["Forma"]) in ["Pix","Dinheiro","Cartão","Transferência"] else "Pix"))
                colN1, colN2 = st.columns(2)
                with colN1:
                    bruto_e = st.number_input("Bruto", min_value=0.0, step=1.0, format="%.2f", value=float(linha["Bruto"]))
                with colN2:
                    liquido_e = st.number_input("Líquido", min_value=0.0, step=1.0, format="%.2f", value=float(linha["Liquido"]), disabled=(forma_e!="Cartão"))

                # recomputa taxa se for cartão
                if forma_e == "Cartão":
                    taxa_val_e = max(0.0, float(bruto_e) - float(liquido_e))
                    taxa_pct_e = (taxa_val_e/float(bruto_e)*100.0) if bruto_e>0 else 0.0
                else:
                    liquido_e = float(bruto_e)
                    taxa_val_e = 0.0
                    taxa_pct_e = 0.0

                colN3, colN4 = st.columns(2)
                with colN3:
                    ref_e = st.text_input("Referência", str(linha.get("Referencia","") or ""))
                with colN4:
                    recibo_e = st.text_input("ReciboURL", str(linha.get("ReciboURL","") or ""))

                obs_e = st.text_input("Obs.", str(linha.get("Obs","") or ""))
                st.caption(f"Taxa: {_fmt_brl(taxa_val_e)} ({_fmt_pct(taxa_pct_e)})")

                cA, cB, cC = st.columns(3)
                salvar = cA.form_submit_button("💾 Salvar alterações", use_container_width=True)
                duplicar = cB.form_submit_button("📄 Duplicar", use_container_width=True)
                pedir_apagar = cC.form_submit_button("🗑️ Apagar", use_container_width=True)

            if salvar:
                # updates
                updates = [
                    ("PacienteID", pac_id_new),
                    ("Data", data_e.strftime("%d/%m/%Y")),
                    ("Forma", forma_e),
                    ("Bruto", float(bruto_e)),
                    ("Liquido", float(liquido_e)),
                    ("TaxaValor", round(float(taxa_val_e), 2)),
                    ("TaxaPct", round(float(taxa_pct_e), 2)),
                    ("Referencia", ref_e.strip()),
                    ("Obs", obs_e.strip()),
                    ("ReciboURL", recibo_e.strip()),
                ]
                for col, val in updates:
                    ci = col_idx.get(col)
                    if ci:
                        ws.update_cell(rownum, ci, val)
                st.success("Pagamento atualizado.")
                st.cache_data.clear()
                st.rerun()

            if duplicar:
                novo_id = new_id("PG")
                append_rows(ws, [{
                    "PagamentoID": novo_id,
                    "PacienteID": pac_id_new,
                    "Data": data_e.strftime("%d/%m/%Y"),
                    "Forma": forma_e,
                    "Bruto": float(bruto_e),
                    "Liquido": float(liquido_e),
                    "TaxaValor": round(float(taxa_val_e), 2),
                    "TaxaPct": round(float(taxa_pct_e), 2),
                    "Referencia": ref_e.strip(),
                    "Obs": obs_e.strip(),
                    "ReciboURL": recibo_e.strip(),
                }], default_headers=PAG_COLS)
                st.success(f"Pagamento duplicado ({novo_id}).")
                st.cache_data.clear()
                st.rerun()

            # etapa 1: marcar exclusão pendente
            if pedir_apagar:
                st.session_state["__pending_delete_pg"] = {
                    "pag_id": pid_sel,
                    "rownum": int(rownum),
                    "desc": escolha,
                }
                st.rerun()

# etapa 2: confirmar exclusão (fora de form)
pend = st.session_state.get("__pending_delete_pg")
if pend:
    st.error("⚠️ Confirma remover permanentemente o pagamento abaixo?")
    st.write(pend["desc"])
    col_c, col_x = st.columns(2)
    if col_c.button("✅ Confirmar exclusão", key="confirm_delete_pag_btn", use_container_width=True):
        try:
            ws.delete_rows(int(pend["rownum"]))
            st.success("Pagamento apagado.")
        except Exception as e:
            st.error(f"Erro ao apagar: {e}")
        finally:
            st.session_state.pop("__pending_delete_pg", None)
            st.cache_data.clear()
            st.rerun()
    if col_x.button("❌ Cancelar", key="cancel_delete_pag_btn", use_container_width=True):
        st.session_state.pop("__pending_delete_pg", None)
        st.info("Exclusão cancelada.")
        st.rerun()
