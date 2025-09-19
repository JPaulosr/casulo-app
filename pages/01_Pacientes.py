# pages/01_Pacientes.py
# -*- coding: utf-8 -*-
import re
from datetime import datetime
import pandas as pd
import streamlit as st

from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Pacientes", page_icon="👨‍👩‍👧", layout="wide")
st.title("👨‍👩‍👧 Pacientes")

# =========================
# Conexão / leitura
# =========================
ss = connect()
PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]
df, ws = read_ws(ss, "Pacientes", PAC_COLS)
df = (df if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=PAC_COLS)).copy()
df = df.reindex(columns=PAC_COLS).fillna("")

# Normalizações leves
def _to_date_str(s):
    if not s: return ""
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.strftime("%d/%m/%Y")
        except Exception:
            pass
    return s

df["DataNascimento"] = df["DataNascimento"].map(_to_date_str)

# =========================
# Sidebar — Filtros
# =========================
with st.sidebar:
    st.header("🔎 Filtros")
    q = st.text_input("Buscar (nome, responsável, tel, email, diagnóstico)", "")
    status_opt = ["(Todos)","Ativo","Pausa","Alta"]
    sel_status = st.selectbox("Status", status_opt, index=0)
    prio_opt = ["(Todas)","Normal","Alta","Urgente"]
    sel_prio = st.selectbox("Prioridade", prio_opt, index=0)
    st.caption("Dica: use a busca para achar por telefone ou parte do nome.")

# =========================
# KPI topo
# =========================
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Total", len(df))
with c2: st.metric("Ativos", int((df["Status"]=="Ativo").sum()))
with c3: st.metric("Pausa", int((df["Status"]=="Pausa").sum()))
with c4: st.metric("Altas", int((df["Status"]=="Alta").sum()))

# =========================
# Aplicar filtros
# =========================
df_view = df.copy()
if sel_status != "(Todos)":
    df_view = df_view[df_view["Status"]==sel_status]
if sel_prio != "(Todas)":
    df_view = df_view[df_view["Prioridade"]==sel_prio]
if q.strip():
    ql = q.strip().lower()
    mask = (
        df_view["Nome"].str.lower().str.contains(ql, na=False) |
        df_view["Responsavel"].str.lower().str.contains(ql, na=False) |
        df_view["Telefone"].str.lower().str.contains(ql, na=False) |
        df_view["Email"].str.lower().str.contains(ql, na=False) |
        df_view["Diagnostico"].str.lower().str.contains(ql, na=False)
    )
    df_view = df_view[mask]

# =========================
# Ações rápidas
# =========================
ac1, ac2, ac3 = st.columns(3)
with ac1:
    st.download_button(
        "⬇️ Exportar CSV",
        data=df_view.to_csv(index=False).encode("utf-8"),
        file_name="pacientes.csv",
        mime="text/csv",
        use_container_width=True
    )
with ac2:
    st.caption("Link WhatsApp rápido")
    tel_raw = st.text_input("Telefone (somente números, c/ DDD)", "", key="wa_tel")
    if st.button("Abrir WhatsApp", use_container_width=True):
        t = re.sub(r"\D+", "", tel_raw or "")
        if t:
            st.markdown(f'[Clique para abrir o WhatsApp](https://wa.me/55{t})')
        else:
            st.warning("Informe um telefone válido (apenas números).")
with ac3:
    st.caption("Dica: edite a tabela abaixo e salve em lote.")

st.markdown("---")

# =========================
# Lista (editável)
# =========================
st.subheader("Lista (editar direto na tabela)")

cols_show = [
    "PacienteID","Nome","Responsavel","Telefone","Email","DataNascimento",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]

# --- Normalização forte de tipos (evita erro do data_editor) ---
df_view = df_view.copy().reindex(columns=PAC_COLS).fillna("")
TEXT_COLS = PAC_COLS[:]  # todas são texto aqui
for c in TEXT_COLS:
    df_view[c] = df_view[c].astype(str)

# --- Opções dinâmicas — incluem existentes + padrão + vazio ---
status_defaults = ["Ativo", "Pausa", "Alta"]
prio_defaults   = ["Normal", "Alta", "Urgente"]
status_opts = sorted(set(df_view["Status"].unique()) | set(status_defaults) | {""})
prio_opts   = sorted(set(df_view["Prioridade"].unique()) | set(prio_defaults) | {""})

df_view.loc[~df_view["Status"].isin(status_opts), "Status"] = ""
df_view.loc[~df_view["Prioridade"].isin(prio_opts), "Prioridade"] = ""

edited_df = st.data_editor(
    df_view[cols_show].reset_index(drop=True),
    hide_index=True,
    use_container_width=True,
    disabled=["PacienteID"],
    column_config={
        "PacienteID": st.column_config.TextColumn("PacienteID"),
        "Nome": st.column_config.TextColumn("Nome", help="Nome completo do paciente"),
        "Responsavel": st.column_config.TextColumn("Responsável"),
        "Telefone": st.column_config.TextColumn("Telefone"),
        "Email": st.column_config.TextColumn("Email"),
        "DataNascimento": st.column_config.TextColumn("Nascimento (DD/MM/AAAA)"),
        "Diagnostico": st.column_config.TextColumn("Diagnóstico(s)", width="large"),
        "Convenio": st.column_config.TextColumn("Convênio"),
        "Status": st.column_config.SelectboxColumn("Status", options=status_opts),
        "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=prio_opts),
        # TextColumn é mais permissivo; troque para LinkColumn quando estiver tudo limpo
        "FotoURL": st.column_config.TextColumn("FotoURL", help="URL de imagem (Drive/Cloudinary)"),
        "Observacoes": st.column_config.TextColumn("Observações", width="large"),
    },
    key="grid_pacientes",
)

# Reconstruir df mesclado (aplica alterações do editor ao df original por PacienteID)
df_to_save = df.copy()
orig_by_id = df_to_save.set_index("PacienteID")
edit_by_id = edited_df.set_index("PacienteID")
common_ids = edit_by_id.index.intersection(orig_by_id.index)
orig_by_id.loc[common_ids, cols_show[1:]] = edit_by_id.loc[common_ids, cols_show[1:]]
df_merged = orig_by_id.reset_index()

save_col1, save_col2 = st.columns([1,1])

with save_col1:
    if st.button("💾 Salvar alterações", type="primary", use_container_width=True):
        try:
            out = df_merged[PAC_COLS].fillna("")
            values = [PAC_COLS] + out.values.tolist()
            ws.update("A1", values)
            st.success("Alterações salvas na planilha ✅")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

with save_col2:
    ids_para_excluir = st.multiselect(
        "Selecionar pacientes para apagar",
        options=sorted(df_view["PacienteID"].unique().tolist()),
        help="Escolha um ou mais PacienteID para exclusão."
    )
    if st.button("🗑️ Excluir selecionados", use_container_width=True, disabled=(len(ids_para_excluir)==0)):
        try:
            df_drop = df_to_save[~df_to_save["PacienteID"].isin(ids_para_excluir)]
            out = df_drop[PAC_COLS].fillna("")
            values = [PAC_COLS] + out.values.tolist()
            ws.update("A1", values)
            st.success(f"{len(ids_para_excluir)} registro(s) excluído(s) ✅")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao excluir: {e}")

# =========================
# Detalhes com preview de foto
# =========================
st.markdown("---")
st.subheader("🔍 Detalhes rápidos (preview de foto)")
for _, row in edited_df.iterrows():
    with st.expander(f"{row['Nome']} — {row['Status']} • {row['Prioridade']}"):
        cimg, cinfo = st.columns([1,3])
        with cimg:
            if str(row.get("FotoURL","")).strip():
                try:
                    st.image(str(row["FotoURL"]), caption=row["Nome"], use_container_width=True)
                except Exception:
                    st.caption("Não foi possível carregar a imagem.")
            else:
                st.caption("Sem foto.")
        with cinfo:
            st.markdown(f"**PacienteID:** {row['PacienteID']}")
            st.markdown(f"**Responsável:** {row['Responsavel'] or '—'}")
            st.markdown(f"**Telefone:** {row['Telefone'] or '—'}")
            st.markdown(f"**Email:** {row['Email'] or '—'}")
            st.markdown(f"**Nascimento:** {row['DataNascimento'] or '—'}")
            st.markdown(f"**Convênio:** {row['Convenio'] or '—'}")
            st.markdown(f"**Diagnóstico:** {row['Diagnostico'] or '—'}")
            st.markdown(f"**Observações:** {row['Observacoes'] or '—'}")

# =========================
# Cadastro — Novo paciente
# =========================
st.markdown("---")
st.subheader("➕ Cadastrar novo")

with st.form("novo_paciente"):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Nome*", "")
        nasc = st.text_input("Data de nascimento (DD/MM/AAAA)", "")
        resp = st.text_input("Responsável", "")
        tel  = st.text_input("Telefone", "")
        email= st.text_input("Email", "")
        conv = st.text_input("Convênio (ou 'Particular')", "")
    with c2:
        diag = st.text_area("Diagnóstico(s)", "")
        status = st.selectbox("Status", ["Ativo","Pausa","Alta"], index=0)
        prio = st.selectbox("Prioridade", ["Normal","Alta","Urgente"], index=0)
        foto = st.text_input("FotoURL (Drive/Cloudinary)", "")
        obs  = st.text_area("Observações", "")
    ok = st.form_submit_button("Salvar")

    if ok:
        if not nome.strip():
            st.error("Informe o nome do paciente.")
        else:
            try:
                pid = new_id("P")
                record = {
                    "PacienteID": pid,
                    "Nome": nome.strip(),
                    "DataNascimento": _to_date_str(nasc),
                    "Responsavel": resp.strip(),
                    "Telefone": tel.strip(),
                    "Email": email.strip(),
                    "Diagnostico": diag.strip(),
                    "Convenio": (conv.strip() or "Particular"),
                    "Status": status,
                    "Prioridade": prio,
                    "FotoURL": foto.strip(),
                    "Observacoes": obs.strip()
                }
                append_rows(ws, [record], default_headers=PAC_COLS)
                st.success(f"Paciente cadastrado: {nome} ({pid}) ✅")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar novo paciente: {e}")
