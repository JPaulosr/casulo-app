# pages/05_Despesas.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Despesas", page_icon="🧾", layout="wide")
st.title("🧾 Despesas")

# ---------------- helpers ----------------
def _fmt_brl(v) -> str:
    try:
        x = float(v)
    except Exception:
        return "R$ 0,00"
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _parse_dt_br(s: str):
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None

def _br_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _cloudinary_ready():
    try:
        csec = st.secrets.get("CLOUDINARY", {})
        return bool(csec and csec.get("cloud_name") and csec.get("api_key") and csec.get("api_secret"))
    except Exception:
        return False

CATEGORIAS_PADRAO = [
    "Aluguel", "Água", "Luz", "Internet", "Telefone",
    "Materiais", "Equipamentos", "Marketing", "Transporte",
    "Serviços Terceiros", "Impostos/Taxas", "Outros"
]
FORMAS = ["Pix","Dinheiro","Cartão","Transferência","Boleto","TED/DOC"]
CENTROS = ["Assistencial", "Administração", "Comercial", "Outros"]

# ---------------- schema ----------------
DESP_COLS = [
    "DespesaID","Data","Categoria","Descricao","Fornecedor","Forma",
    "Valor","CentroCusto","Pago","Referencia","Obs","ComprovanteURL",
    "RecorrenteID","Parcela"
]

# ---------------- dados ----------------
ss = connect()
df_desp, ws = read_ws(ss, "Despesas", DESP_COLS)

# índices de coluna p/ update
headers = ws.row_values(1)
col_idx = {h: i+1 for i, h in enumerate(headers)}  # 1-based

# prepara df
df_desp = df_desp.copy()
df_desp["__rownum"] = df_desp.index + 2
df_desp["__d"] = df_desp["Data"].apply(_parse_dt_br)

for c in ["Valor"]:
    df_desp[c] = pd.to_numeric(df_desp[c], errors="coerce").fillna(0.0)

# ===================== TABS =====================
tab_hist, tab_cad, tab_rec, tab_edit = st.tabs([
    "📚 Histórico & Relatórios", "📝 Lançar despesa", "🔁 Recorrências", "🛠️ Editar / Apagar"
])

# ============================================================
# 📚 HISTÓRICO
# ============================================================
with tab_hist:
    st.subheader("Histórico & Relatórios")

    colf1, colf2, colf3, colf4 = st.columns([1,1,1,1])
    with colf1:
        de = st.date_input("De", value=date.today().replace(day=1))
    with colf2:
        ate = st.date_input("Até", value=date.today())
    with colf3:
        cat = st.selectbox("Categoria", ["(todas)"] + sorted(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).unique().tolist()))
    with colf4:
        pago_opt = st.selectbox("Status", ["(todos)","Pago","Em aberto"], index=0)

    colx1, colx2 = st.columns([1,1])
    with colx1:
        fornecedor = st.text_input("Fornecedor (contém)", "")
    with colx2:
        centro = st.selectbox("Centro de custo", ["(todos)"] + CENTROS, index=0)

    ref_txt = st.text_input("Referência (contém, ex.: 09/2025)", "")

    vis = df_desp.copy()
    if de:   vis = vis[vis["__d"] >= de]
    if ate:  vis = vis[vis["__d"] <= ate]
    if cat != "(todas)":
        vis = vis[vis["Categoria"].astype(str) == cat]
    if fornecedor.strip():
        vis = vis[vis["Fornecedor"].astype(str).str.contains(fornecedor.strip(), case=False, na=False)]
    if centro != "(todos)":
        vis = vis[vis["CentroCusto"].astype(str) == centro]
    if pago_opt != "(todos)":
        vis = vis[vis["Pago"].astype(str).str.lower() == ("true" if pago_opt=="Pago" else "false")]
    if ref_txt.strip():
        vis = vis[vis["Referencia"].astype(str).str.contains(ref_txt.strip(), case=False, na=False)]

    total = vis["Valor"].sum()
    total_pago = vis[vis["Pago"].astype(str).str.lower()=="true"]["Valor"].sum()
    total_aberto = total - total_pago

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Qtde", f"{len(vis)}")
    c2.metric("Total", _fmt_brl(total))
    c3.metric("Pago", _fmt_brl(total_pago))
    c4.metric("Em aberto", _fmt_brl(total_aberto))

    cols_show = ["Data","Categoria","Descricao","Fornecedor","Forma","Valor","CentroCusto","Pago","Referencia","Obs","DespesaID"]
    st.dataframe(
        vis[cols_show].sort_values(["Data","Categoria"], ascending=[False, True]),
        use_container_width=True, hide_index=True
    )

    st.markdown("---")
    st.markdown("#### 📊 Resumos")
    if not vis.empty:
        tmp = vis.copy()
        tmp["MesRef"] = tmp["__d"].apply(lambda d: d.strftime("%Y-%m") if d else "")
        grp_mes = (tmp.groupby("MesRef", as_index=False)["Valor"].sum().sort_values("MesRef", ascending=False))
        grp_cat = (tmp.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False))
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("Por mês (data)")
            st.dataframe(grp_mes, use_container_width=True, hide_index=True)
        with col_b:
            st.write("Por categoria")
            st.dataframe(grp_cat, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados no filtro para resumir.")

    st.markdown("---")
    st.download_button(
        "⬇️ Exportar CSV (filtro aplicado)",
        data=vis[cols_show].to_csv(index=False).encode("utf-8-sig"),
        file_name="despesas_filtradas.csv"
    )

# ============================================================
# 📝 LANÇAR DESPESA
# ============================================================
with tab_cad:
    st.subheader("Lançar despesa")

    categorias = sorted(list(set(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).tolist())))

    with st.form("nova_despesa"):
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            data_d = st.date_input("Data", value=date.today())
        with col2:
            cat_sel = st.selectbox("Categoria", options=categorias + ["(outra...)"], index=0)
        with col3:
            forma = st.selectbox("Forma", FORMAS, index=0)

        outra = ""
        if cat_sel == "(outra...)":
            outra = st.text_input("Nova categoria", "")
        desc = st.text_input("Descrição", "")
        fornecedor_n = st.text_input("Fornecedor", "")
        valor = st.number_input("Valor", min_value=0.0, step=1.0, format="%.2f", value=0.00)

        col4, col5 = st.columns([1,1])
        with col4:
            centro = st.selectbox("Centro de custo", CENTROS, index=0)
        with col5:
            pago = st.checkbox("Pago?", value=False)

        col6, col7 = st.columns([1,1])
        with col6:
            ref = st.text_input("Referência (ex.: 09/2025)", "")
        with col7:
            obs = st.text_input("Obs.", "")

        comp_url = ""
        uploaded = None
        use_cloud = _cloudinary_ready()
        if use_cloud:
            uploaded = st.file_uploader("Comprovante (imagem/PDF) — enviaremos ao Cloudinary", type=["png","jpg","jpeg","pdf"])
        else:
            comp_url = st.text_input("ComprovanteURL (cole a URL do arquivo)", "")

        salvar = st.form_submit_button("Salvar")

    if salvar:
        categoria_final = outra.strip() if cat_sel == "(outra...)" and outra.strip() else cat_sel
        if not categoria_final:
            st.error("Informe a categoria.")
            st.stop()
        if valor <= 0:
            st.error("Valor deve ser maior que zero.")
            st.stop()

        # opcional: upload Cloudinary
        if uploaded and use_cloud:
            try:
                import cloudinary
                import cloudinary.uploader
                csec = st.secrets["CLOUDINARY"]
                cloudinary.config(
                    cloud_name=csec["cloud_name"],
                    api_key=csec["api_key"],
                    api_secret=csec["api_secret"]
                )
                folder = csec.get("folder_expenses", "casulo/expenses")
                public_id = f"desp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                res = cloudinary.uploader.upload(uploaded, folder=folder, public_id=public_id, overwrite=True, resource_type="auto")
                comp_url = res.get("secure_url","")
            except Exception as e:
                st.warning(f"Falha ao enviar para Cloudinary: {e}. Você pode colar a URL manualmente depois na edição.")

        did = new_id("D")
        append_rows(ws, [{
            "DespesaID": did,
            "Data": _br_date(data_d),
            "Categoria": categoria_final,
            "Descricao": desc.strip(),
            "Fornecedor": fornecedor_n.strip(),
            "Forma": forma,
            "Valor": float(valor),
            "CentroCusto": centro,
            "Pago": bool(pago),
            "Referencia": ref.strip(),
            "Obs": obs.strip(),
            "ComprovanteURL": comp_url.strip(),
            "RecorrenteID": "",
            "Parcela": ""
        }], default_headers=DESP_COLS)

        st.success(f"Despesa lançada ({did}).")
        st.cache_data.clear()
        st.rerun()

# ============================================================
# 🔁 RECORRÊNCIAS
# ============================================================
with tab_rec:
    st.subheader("Criar despesas recorrentes")

    with st.form("nova_recorrencia_desp"):
        data_ini = st.date_input("Data inicial", value=date.today())
        periodic = st.radio("Periodicidade", ["Mensal","Semanal"], horizontal=True)
        repeticoes = st.number_input("Quantidade de lançamentos", min_value=1, max_value=60, value=6, step=1)

        cat_r = st.selectbox("Categoria", options=sorted(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).tolist()) + ["(outra...)"])
        cat_r_out = st.text_input("Nova categoria (se marcou outra)", "")
        desc_r = st.text_input("Descrição", "")
        forn_r = st.text_input("Fornecedor", "")
        forma_r = st.selectbox("Forma", FORMAS, index=0)
        valor_r = st.number_input("Valor", min_value=0.0, step=1.0, format="%.2f", value=0.00)
        centro_r = st.selectbox("Centro de custo", CENTROS, index=0)
        pago_r = st.checkbox("Marcar como pago?", value=False)
        ref_base = st.text_input("Referência base (opcional, ex.: 09/2025)", "")
        obs_r = st.text_input("Obs.", "Recorrente")

        criar = st.form_submit_button("Gerar lançamentos")

    if criar:
        categoria_final = cat_r_out.strip() if cat_r == "(outra...)" and cat_r_out.strip() else cat_r
        if not categoria_final:
            st.error("Informe a categoria.")
            st.stop()
        if valor_r <= 0:
            st.error("Valor deve ser maior que zero.")
            st.stop()

        rid = new_id("DR")  # recorrente id
        itens = []
        for i in range(repeticoes):
            if periodic == "Mensal":
                d = (data_ini.replace(day=1) + pd.DateOffset(months=i)).to_pydatetime().date().replace(day=min(data_ini.day, 28))
            else:
                d = data_ini + timedelta(weeks=i)

            ref_use = ref_base.strip() if ref_base.strip() else d.strftime("%m/%Y")
            itens.append({
                "DespesaID": new_id("D"),
                "Data": _br_date(d),
                "Categoria": categoria_final,
                "Descricao": desc_r.strip(),
                "Fornecedor": forn_r.strip(),
                "Forma": forma_r,
                "Valor": float(valor_r),
                "CentroCusto": centro_r,
                "Pago": bool(pago_r),
                "Referencia": ref_use,
                "Obs": obs_r.strip(),
                "ComprovanteURL": "",
                "RecorrenteID": rid,
                "Parcela": f"{i+1}/{int(repeticoes)}"
            })

        append_rows(ws, itens, default_headers=DESP_COLS)
        st.success(f"✅ Criadas {len(itens)} despesas recorrentes (ID {rid}).")
        st.cache_data.clear()
        st.rerun()

# ============================================================
# 🛠️ EDITAR / APAGAR
# ============================================================
with tab_edit:
    st.subheader("Editar / Apagar")

    if df_desp.empty:
        st.info("Ainda não há despesas.")
        st.stop()

    colE1, colE2 = st.columns(2)
    with colE1:
        de_e = st.date_input("De", value=date.today().replace(day=1), key="ed_desp_de")
    with colE2:
        ate_e = st.date_input("Até", value=date.today(), key="ed_desp_ate")
    cat_e = st.selectbox("Categoria", ["(todas)"] + sorted(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).unique().tolist()), key="ed_cat")
    pago_e = st.selectbox("Status", ["(todos)","Pago","Em aberto"], index=0, key="ed_pago")

    lista = df_desp.copy()
    if de_e:  lista = lista[lista["__d"] >= de_e]
    if ate_e: lista = lista[lista["__d"] <= ate_e]
    if cat_e != "(todas)":
        lista = lista[lista["Categoria"].astype(str) == cat_e]
    if   pago_e == "Pago":
        lista = lista[lista["Pago"].astype(str).str.lower()=="true"]
    elif pago_e == "Em aberto":
        lista = lista[lista["Pago"].astype(str).str.lower()!="true"]

    if lista.empty:
        st.info("Nenhuma despesa no filtro.")
    else:
        lista = lista.sort_values(["Data","Categoria"], ascending=[False, True])

        def _label(r):
            pago_flag = "✅" if str(r["Pago"]).lower()=="true" else "⏳"
            return f"{pago_flag} {r['Data']} • {r['Categoria']} • {_fmt_brl(r['Valor'])} • {r.get('Descricao','') or '-'} • ({r['DespesaID']})"

        options = { _label(r): (r["DespesaID"], int(r["__rownum"])) for _, r in lista.iterrows() }
        escolha = st.selectbox("Escolha a despesa", list(options.keys()))
        did_sel, rownum = options.get(escolha, (None, None))

        if did_sel and rownum:
            linha = df_desp[df_desp["DespesaID"] == did_sel].head(1).iloc[0]

            st.markdown(f"**Despesa:** `{did_sel}`  •  Linha: {rownum}")
            with st.form("edit_desp"):
                data_e = st.date_input("Data", value=_parse_dt_br(linha["Data"]) or date.today())
                cat_e2 = st.selectbox("Categoria", sorted(list(set(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).tolist())) + ["(outra...)"]),
                                      index=0 if linha["Categoria"] not in CATEGORIAS_PADRAO else sorted(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).tolist()).index(linha["Categoria"]) if linha["Categoria"] in sorted(CATEGORIAS_PADRAO + df_desp["Categoria"].dropna().astype(str).tolist()) else 0)
                cat_out = st.text_input("Nova categoria (se outra)", "")
                desc_e = st.text_input("Descrição", str(linha.get("Descricao","") or ""))
                forn_e = st.text_input("Fornecedor", str(linha.get("Fornecedor","") or ""))
                forma_e = st.selectbox("Forma", FORMAS,
                                       index=FORMAS.index(str(linha.get("Forma","Pix"))) if str(linha.get("Forma","Pix")) in FORMAS else 0)
                valor_e = st.number_input("Valor", min_value=0.0, step=1.0, format="%.2f", value=float(linha["Valor"]))
                centro_e = st.selectbox("Centro de custo", CENTROS,
                                        index=CENTROS.index(str(linha.get("CentroCusto","Assistencial"))) if str(linha.get("CentroCusto","Assistencial")) in CENTROS else 0)
                pago_flag = st.checkbox("Pago?", value=(str(linha.get("Pago","")).lower()=="true"))
                colN3, colN4 = st.columns(2)
                with colN3:
                    ref_e = st.text_input("Referência", str(linha.get("Referencia","") or ""))
                with colN4:
                    comp_e = st.text_input("ComprovanteURL", str(linha.get("ComprovanteURL","") or ""))

                obs_e = st.text_input("Obs.", str(linha.get("Obs","") or ""))
                cA, cB, cC = st.columns(3)
                salvar = cA.form_submit_button("💾 Salvar alterações", use_container_width=True)
                duplicar = cB.form_submit_button("📄 Duplicar", use_container_width=True)
                pedir_apagar = cC.form_submit_button("🗑️ Apagar", use_container_width=True)

            if salvar:
                cat_final = cat_out.strip() if cat_e2 == "(outra...)" and cat_out.strip() else cat_e2
                updates = [
                    ("Data", _br_date(data_e)),
                    ("Categoria", cat_final),
                    ("Descricao", desc_e.strip()),
                    ("Fornecedor", forn_e.strip()),
                    ("Forma", forma_e),
                    ("Valor", float(valor_e)),
                    ("CentroCusto", centro_e),
                    ("Pago", bool(pago_flag)),
                    ("Referencia", ref_e.strip()),
                    ("Obs", obs_e.strip()),
                    ("ComprovanteURL", comp_e.strip()),
                ]
                for col, val in updates:
                    ci = col_idx.get(col)
                    if ci: ws.update_cell(rownum, ci, val)
                st.success("Despesa atualizada.")
                st.cache_data.clear(); st.rerun()

            if duplicar:
                novo_id = new_id("D")
                append_rows(ws, [{
                    "DespesaID": novo_id,
                    "Data": _br_date(data_e),
                    "Categoria": cat_out.strip() if cat_e2 == "(outra...)" and cat_out.strip() else cat_e2,
                    "Descricao": desc_e.strip(),
                    "Fornecedor": forn_e.strip(),
                    "Forma": forma_e,
                    "Valor": float(valor_e),
                    "CentroCusto": centro_e,
                    "Pago": bool(pago_flag),
                    "Referencia": ref_e.strip(),
                    "Obs": obs_e.strip(),
                    "ComprovanteURL": comp_e.strip(),
                    "RecorrenteID": str(linha.get("RecorrenteID","") or ""),
                    "Parcela": ""
                }], default_headers=DESP_COLS)
                st.success(f"Despesa duplicada ({novo_id}).")
                st.cache_data.clear(); st.rerun()

            # etapa 1: marcar exclusão pendente
            if pedir_apagar:
                st.session_state["__pending_delete_desp"] = {
                    "desp_id": did_sel,
                    "rownum": int(rownum),
                    "desc": escolha,
                }
                st.rerun()

# etapa 2: confirmar exclusão (fora de form)
pend = st.session_state.get("__pending_delete_desp")
if pend:
    st.error("⚠️ Confirma remover permanentemente a despesa abaixo?")
    st.write(pend["desc"])
    col_c, col_x = st.columns(2)
    if col_c.button("✅ Confirmar exclusão", key="confirm_delete_desp_btn", use_container_width=True):
        try:
            ws.delete_rows(int(pend["rownum"]))
            st.success("Despesa apagada.")
        except Exception as e:
            st.error(f"Erro ao apagar: {e}")
        finally:
            st.session_state.pop("__pending_delete_desp", None)
            st.cache_data.clear(); st.rerun()
    if col_x.button("❌ Cancelar", key="cancel_delete_desp_btn", use_container_width=True):
        st.session_state.pop("__pending_delete_desp", None)
        st.info("Exclusão cancelada."); st.rerun()
