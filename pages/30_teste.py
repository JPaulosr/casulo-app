# pages/01_Pacientes.py
# -*- coding: utf-8 -*-
import re
from datetime import datetime
import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import APIError
import requests  # para o Telegram

from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Pacientes", page_icon="👨‍👩‍👧", layout="wide")

# =========================
# Constantes / schema
# =========================
PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]

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

# =========================
# Telegram helpers
# =========================
TELEGRAM_TOKEN_FALLBACK = ""
TELEGRAM_CHATID_FALLBACK = ""

def _tg_token():
    try:
        tok = (st.secrets.get("TELEGRAM_TOKEN", "") or "").strip()
        return tok or TELEGRAM_TOKEN_FALLBACK
    except Exception:
        return TELEGRAM_TOKEN_FALLBACK

def _tg_chat_id():
    try:
        cid = (st.secrets.get("TELEGRAM_CHAT_ID", "") or "").strip()
        return cid or TELEGRAM_CHATID_FALLBACK
    except Exception:
        return TELEGRAM_CHATID_FALLBACK

def tg_send_message(text: str) -> tuple[bool, str]:
    token = _tg_token()
    chat_id = _tg_chat_id()
    if not token or not chat_id:
        # silencioso: apenas informa que não está configurado
        return False, "TELEGRAM_TOKEN ou CHAT_ID ausente."
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=30)
        ok = (r.status_code == 200 and r.json().get("ok"))
        return (ok, "" if ok else r.text)
    except Exception as e:
        return False, str(e)

# =========================
# UI sugar: CSS moderno (igual ao 02_Paciente_Detalhe)
# =========================
st.markdown("""
<style>
:root {
  --card-bg: rgba(255,255,255,0.05);
  --card-bd: rgba(255,255,255,0.12);
  --muted: rgba(255,255,255,0.6);
}
html, body, [data-testid="stAppViewContainer"] { scroll-behavior: smooth; }
.block-container { padding-top: 1.1rem; }
h1,h2,h3 { letter-spacing:.2px; }
.header-card {
  border: 1px solid var(--card-bd);
  background: linear-gradient(180deg, var(--card-bg), transparent);
  padding: 16px; border-radius: 16px; margin: .2rem 0 1rem 0;
}
.kpi-card {
  border: 1px solid var(--card-bd);
  background: var(--card-bg);
  padding: 14px 16px; border-radius: 14px;
}
.kpi-title { font-size: .78rem; color: var(--muted); margin-bottom: 6px; }
.kpi-value { font-size: 1.25rem; font-weight: 700; }
.badge {
  display:inline-block; padding: 2px 8px; border-radius: 999px;
  font-size:.75rem; font-weight:600; border:1px solid var(--card-bd);
  background: rgba(255,255,255,.06); margin-right:6px; margin-bottom:4px;
}
.badge.ok   { background: rgba(46,160,67,.18);  border-color: rgba(46,160,67,.35); }
.badge.warn { background: rgba(255,171,0,.18); border-color: rgba(255,171,0,.35); }
.badge.err  { background: rgba(244,67,54,.18); border-color: rgba(244,67,54,.35); }
.action-bar {
  position: sticky; top: 0; z-index: 5;
  padding: 10px 12px; border-radius: 12px;
  background: linear-gradient(180deg, rgba(0,0,0,.18), rgba(0,0,0,.06));
  border: 1px solid var(--card-bd); backdrop-filter: blur(8px);
  margin-bottom: .6rem;
}
.doc-item {
  padding: 8px 10px; border-radius: 12px;
  border: 1px solid var(--card-bd); margin-bottom: 8px;
  background: var(--card-bg);
}
.avatar {
  width: 64px; height: 64px; border-radius: 12px;
  object-fit: cover; border: 1px solid var(--card-bd);
}
.small-muted { color: var(--muted); font-size: .9rem; }
.exp-chip { font-size:.8rem; color:var(--muted); }
</style>
""", unsafe_allow_html=True)

# =========================
# Conexão + leitura robusta
# =========================
ss = connect()

def _render_perm_help(err: Exception):
    st.error("Falha de acesso à planilha (provável permissão/escopo).")
    sa_email = None
    try:
        sa_email = st.secrets.get("gcp_service_account", {}).get("client_email", None)
    except Exception:
        pass
    if not sa_email:
        for key in ("service_account", "gspread_service_account", "gcp"):
            try:
                sa_email = st.secrets.get(key, {}).get("client_email", None) or sa_email
            except Exception:
                pass
    if sa_email:
        st.info(f"Compartilhe a planilha com o e-mail da Service Account: <b>{sa_email}</b> (Editor).", unsafe_allow_html=True)
    else:
        st.info("Compartilhe a planilha com o e-mail da sua Service Account (`...iam.gserviceaccount.com`).")
    st.caption("Depois de compartilhar, atualize a página.")

def _safe_load_sheet(ss, title: str, cols: list[str]) -> tuple[pd.DataFrame, gspread.Worksheet]:
    """Tenta read_ws; se falhar, cria a aba e cabeçalhos. Exibe diagnósticos úteis."""
    try:
        df, ws = read_ws(ss, title, cols)
        df = (df if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=cols))
        df = df.reindex(columns=cols).fillna("")
        return df, ws
    except APIError as e:
        st.warning("Não consegui ler a aba. Vou diagnosticar e tentar recuperar automaticamente…")
        existing = []
        try:
            existing = [w.title for w in ss.worksheets()]
        except Exception:
            pass
        if existing:
            st.info(f"Aba(s) existentes na planilha: {', '.join(existing)}")
        if title not in existing:
            st.info(f"A aba **{title}** não existe. Vou criar agora com o cabeçalho padrão.")
            try:
                ws = ss.add_worksheet(title=title, rows=200, cols=max(20, len(cols)))
                ws.update("A1", [cols])
                st.success(f"Aba **{title}** criada com sucesso ✅")
                return pd.DataFrame(columns=cols), ws
            except APIError as e_create:
                _render_perm_help(e_create)
                raise
        else:
            _render_perm_help(e)
            raise
    except Exception as e:
        st.error(f"Erro inesperado ao abrir a planilha: {e}")
        raise

df, ws = _safe_load_sheet(ss, "Pacientes", PAC_COLS)
df["DataNascimento"] = df["DataNascimento"].map(_to_date_str)

# =========================
# Header
# =========================
st.markdown('<div class="header-card">', unsafe_allow_html=True)
st.title("👨‍👩‍👧 Pacientes")
st.caption("Gestão central de pacientes — editar, filtrar, exportar e cadastrar.")
top_badges = [
    '<span class="badge">Convênio / Particular</span>',
    '<span class="badge ok">Ativo</span>',
    '<span class="badge warn">Pausa</span>',
    '<span class="badge err">Alta</span>',
]
st.markdown(" ".join(top_badges), unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

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
# KPI topo (cards)
# =========================
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">Total</div><div class="kpi-value">{len(df)}</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">Ativos</div><div class="kpi-value">{int((df["Status"]=="Ativo").sum())}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">Pausa</div><div class="kpi-value">{int((df["Status"]=="Pausa").sum())}</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">Altas</div><div class="kpi-value">{int((df["Status"]=="Alta").sum())}</div></div>', unsafe_allow_html=True)

st.markdown("")

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
# Barra de ações (fixa)
# =========================
st.markdown('<div class="action-bar">', unsafe_allow_html=True)
ac1, ac2, ac3 = st.columns([1,1,2])
with ac1:
    st.download_button(
        "⬇️ Exportar CSV",
        data=df_view.to_csv(index=False).encode("utf-8"),
        file_name="pacientes.csv",
        mime="text/csv",
        use_container_width=True
    )
with ac2:
    tel_raw = st.text_input("Telefone p/ WhatsApp (somente números)", "", key="wa_tel")
    if st.button("Abrir WhatsApp", use_container_width=True):
        t = re.sub(r"\D+", "", tel_raw or "")
        if t:
            st.markdown(f'[Clique para abrir o WhatsApp](https://wa.me/55{t})')
        else:
            st.warning("Informe um telefone válido (apenas números).")
with ac3:
    st.caption("Edite a tabela abaixo e clique em **Salvar alterações**.")
st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Lista (editável)
# =========================
st.subheader("📋 Lista de Pacientes")

cols_show = [
    "PacienteID","Nome","Responsavel","Telefone","Email","DataNascimento",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]

# Normalização de tipos (evita erro do data_editor)
df_view = df_view.copy().reindex(columns=PAC_COLS).fillna("")
for c in PAC_COLS:
    df_view[c] = df_view[c].astype(str)

# Opções dinâmicas
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
        "FotoURL": st.column_config.TextColumn("FotoURL", help="URL de imagem (Drive/Cloudinary)"),
        "Observacoes": st.column_config.TextColumn("Observações", width="large"),
    },
    key="grid_pacientes",
)

# Reconstruir df mesclado para salvar
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
        except APIError as e:
            _render_perm_help(e)
            st.error("Erro do Google Sheets ao salvar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

with save_col2:
    # ===== Mostrar NOME no seletor, excluir por ID =====
    pid_to_nome = {str(r["PacienteID"]): str(r["Nome"]) for _, r in df_to_save.iterrows()}
    options_ids = sorted(df_view["PacienteID"].unique().tolist())

    ids_para_excluir = st.multiselect(
        "Selecionar pacientes para apagar (mostra nomes)",
        options=options_ids,
        format_func=lambda pid: f'{pid_to_nome.get(pid, "(sem nome)")} — {pid}',
        help="A exclusão é feita pelo ID, mas a lista exibe o Nome para facilitar."
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
        except APIError as e:
            _render_perm_help(e)
            st.error("Erro do Google Sheets ao excluir.")
        except Exception as e:
            st.error(f"Erro ao excluir: {e}")

# =========================
# Detalhes rápidos (com avatar/foto, no estilo do detalhe)
# =========================
st.markdown("---")
st.subheader("🔍 Detalhes rápidos")

if edited_df.empty:
    st.caption("Nenhum paciente nos filtros atuais.")
else:
    for _, row in edited_df.iterrows():
        nome = str(row.get("Nome","")).strip() or "(sem nome)"
        status = str(row.get("Status","")).strip() or "-"
        prio = str(row.get("Prioridade","")).strip() or "-"
        with st.expander(f"{nome} — {status} • {prio}"):
            cimg, cinfo = st.columns([1,3])
            with cimg:
                foto = str(row.get("FotoURL","")).strip()
                if foto:
                    try:
                        st.image(foto, caption=None, use_container_width=True)
                    except Exception:
                        st.caption("Não foi possível carregar a imagem.")
                else:
                    st.markdown(f"""
                        <div class="avatar" style="display:flex;align-items:center;justify-content:center;font-weight:800;">
                            {nome[0:2].upper()}
                        </div>
                    """, unsafe_allow_html=True)
                    st.caption("Sem foto")
            with cinfo:
                st.markdown(
                    " ".join([
                        f'<span class="badge {"ok" if status=="Ativo" else ("warn" if status=="Pausa" else "err")}">Status: {status}</span>',
                        f'<span class="badge">Prioridade: {prio}</span>',
                        f'<span class="badge">Convênio: {str(row.get("Convenio","") or "Particular")}</span>',
                    ]),
                    unsafe_allow_html=True
                )
                st.markdown(f"**PacienteID:** {row['PacienteID']}")
                st.markdown(f"**Responsável:** {row.get('Responsavel') or '—'}")
                st.markdown(f"**Telefone:** {row.get('Telefone') or '—'}")
                st.markdown(f"**Email:** {row.get('Email') or '—'}")
                st.markdown(f"**Nascimento:** {row.get('DataNascimento') or '—'}")
                st.markdown(f"**Convênio:** {row.get('Convenio') or '—'}")
                st.markdown(f"**Diagnóstico:** {row.get('Diagnostico') or '—'}")
                st.markdown(f"**Observações:** {row.get('Observacoes') or '—'}")

# =========================
# Cadastro — Novo paciente (envia Telegram)
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
                    "Responsavel": (resp or "").strip(),
                    "Telefone": (tel or "").strip(),
                    "Email": (email or "").strip(),
                    "Diagnostico": (diag or "").strip(),
                    "Convenio": (conv or "").strip() or "Particular",
                    "Status": status,
                    "Prioridade": prio,
                    "FotoURL": (foto or "").strip(),
                    "Observacoes": (obs or "").strip()
                }
                append_rows(ws, [record], default_headers=PAC_COLS)
                st.success(f"Paciente cadastrado: {nome} ({pid}) ✅")

                # ---- Telegram: notificação de novo cadastro ----
                txt = (
                    f"🧾 <b>Novo paciente cadastrado</b>\n"
                    f"👤 <b>Nome:</b> {nome}\n"
                    f"🆔 <b>ID:</b> {pid}\n"
                    f"👨‍👩‍👧 <b>Responsável:</b> {resp or '—'}\n"
                    f"📞 <b>Telefone:</b> {tel or '—'}\n"
                    f"🏷️ <b>Convênio:</b> {(conv or 'Particular')}\n"
                    f"⚙️ <b>Status:</b> {status} • <b>Prioridade:</b> {prio}"
                )
                ok_tg, err_tg = tg_send_message(txt)
                if ok_tg:
                    st.toast("Notificado no Telegram ✅", icon="✅")
                else:
                    st.caption(f"(Telegram não configurado: {err_tg})")

                st.cache_data.clear()
                st.rerun()
            except APIError as e:
                _render_perm_help(e)
                st.error("Erro do Google Sheets ao salvar novo paciente.")
            except Exception as e:
                st.error(f"Erro ao salvar novo paciente: {e}")
