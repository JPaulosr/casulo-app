# pages/01_Pacientes.py
# -*- coding: utf-8 -*-
import re
from datetime import datetime
import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import APIError
import requests

from utils_casulo import connect, read_ws, append_rows, new_id
# usa seu util existente (não precisa alterar)
from utils_telegram import _token as tg_token, default_chat_id as tg_default_chat_id, tg_send_text

st.set_page_config(page_title="Casulo — Pacientes", page_icon="👨‍👩‍👧", layout="wide")

# ===== Config / schema =====
PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]

LOGO_FALLBACK_URL = ""  # opcional; se vazio usará st.secrets["TELEGRAM_LOGO_FALLBACK"] se existir

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

def _photo_or_logo(p: dict) -> str:
    foto = str(p.get("FotoURL","") or "").strip()
    if foto:
        return foto
    try:
        logo_secret = (st.secrets.get("TELEGRAM_LOGO_FALLBACK","") or "").strip()
    except Exception:
        logo_secret = ""
    return foto or logo_secret or LOGO_FALLBACK_URL or ""

def _fmt_html(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _diff_changes(old_rec: dict, new_rec: dict, campos=None):
    if campos is None:
        campos = ["Nome","Responsavel","Telefone","Email","DataNascimento",
                  "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
    diffs = []
    for c in campos:
        a = str(old_rec.get(c,"") or "").strip()
        b = str(new_rec.get(c,"") or "").strip()
        if a != b:
            diffs.append((c, a, b))
    return diffs

def _tg_send_photo_card(caption_html: str, photo_url: str):
    tok = tg_token()
    if not tok:
        st.warning("⚠️ TELEGRAM_TOKEN ausente em secrets.")
        return
    chat_id = tg_default_chat_id()
    try:
        if photo_url:
            url = f"https://api.telegram.org/bot{tok}/sendPhoto"
            data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML", "disable_web_page_preview": True}
            data["photo"] = photo_url
            r = requests.post(url, data=data, timeout=30)
        else:
            # fallback para texto
            ok, err = tg_send_text(caption_html, chat_id)
            if not ok:
                st.warning(f"⚠️ Telegram (texto) falhou: {err}")
            return
        if not r.ok:
            st.warning(f"⚠️ Telegram respondeu {r.status_code}: {r.text[:200]}")
        else:
            st.toast("Notificação enviada ao Telegram ✅", icon="✅")
    except Exception as e:
        st.warning(f"⚠️ Falha ao enviar para o Telegram: {e}")

def _tg_card_paciente(action: str, p: dict, diffs=None):
    """action: 'Novo' ou 'Editado'"""
    nome = p.get("Nome") or "(sem nome)"
    pid  = p.get("PacienteID") or "-"
    status = p.get("Status") or "-"
    prio   = p.get("Prioridade") or "-"
    linhas = []
    if action.lower() == "editado":
        if diffs:
            linhas.append("<b>Atualizações</b>:")
            for campo, antes, depois in diffs:
                linhas.append(f"• <b>{_fmt_html(campo)}:</b> {_fmt_html(antes)} → <code>{_fmt_html(depois)}</code>")
        else:
            linhas.append("• Sem diferenças detectadas.")
    else:
        linhas.append("• Cadastro realizado com sucesso.")

    caption = (
        f"<b>Paciente {action}</b>\n"
        f"<b>{_fmt_html(nome)}</b>  <i>({pid})</i>\n"
        f"Status: <b>{_fmt_html(status)}</b> • Prioridade: <b>{_fmt_html(prio)}</b>\n\n"
        + "\n".join(linhas)
    )
    _tg_send_photo_card(caption, _photo_or_logo(p))

# ===== CSS =====
st.markdown("""
<style>
:root { --card-bg: rgba(255,255,255,0.05); --card-bd: rgba(255,255,255,0.12); --muted: rgba(255,255,255,0.6); }
.block-container { padding-top: 1.1rem; }
.header-card{border:1px solid var(--card-bd);background:linear-gradient(180deg,var(--card-bg),transparent);padding:16px;border-radius:16px;margin:.2rem 0 1rem 0;}
.kpi-card{border:1px solid var(--card-bd);background:var(--card-bg);padding:14px 16px;border-radius:14px;}
.kpi-title{font-size:.78rem;color:var(--muted);margin-bottom:6px;}
.kpi-value{font-size:1.25rem;font-weight:700;}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:600;border:1px solid var(--card-bd);background:rgba(255,255,255,.06);margin-right:6px;margin-bottom:4px;}
.badge.ok{background:rgba(46,160,67,.18);border-color:rgba(46,160,67,.35);}
.badge.warn{background:rgba(255,171,0,.18);border-color:rgba(255,171,0,.35);}
.badge.err{background:rgba(244,67,54,.18);border-color:rgba(244,67,54,.35);}
.action-bar{position:sticky;top:0;z-index:5;padding:10px 12px;border-radius:12px;background:linear-gradient(180deg,rgba(0,0,0,.18),rgba(0,0,0,.06));border:1px solid var(--card-bd);backdrop-filter:blur(8px);margin-bottom:.6rem;}
.avatar{width:64px;height:64px;border-radius:12px;object-fit:cover;border:1px solid var(--card-bd);}
</style>
""", unsafe_allow_html=True)

# ===== Conexão / leitura segura =====
ss = connect()

def _render_perm_help(err: Exception):
    st.error("Falha de acesso à planilha (provável permissão).")
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
        st.info(f"Compartilhe a planilha com: **{sa_email}** (Editor).")

def _safe_load_sheet(ss, title: str, cols: list[str]):
    try:
        df, ws = read_ws(ss, title, cols)
        df = (df if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=cols))
        df = df.reindex(columns=cols).fillna("")
        return df, ws
    except APIError as e:
        st.warning("Não consegui ler a aba; tentando diagnosticar…")
        existing = []
        try:
            existing = [w.title for w in ss.worksheets()]
        except Exception:
            pass
        if title not in existing:
            try:
                ws = ss.add_worksheet(title=title, rows=300, cols=max(20, len(cols)))
                ws.update("A1", [cols])
                return pd.DataFrame(columns=cols), ws
            except APIError as e2:
                _render_perm_help(e2)
                raise
        else:
            _render_perm_help(e)
            raise

df, ws = _safe_load_sheet(ss, "Pacientes", PAC_COLS)
df["DataNascimento"] = df["DataNascimento"].map(_to_date_str)

# ===== Header =====
st.markdown('<div class="header-card">', unsafe_allow_html=True)
st.title("👨‍👩‍👧 Pacientes")
st.caption("Gestão central de pacientes — editar, filtrar, exportar e cadastrar.")
st.markdown('</div>', unsafe_allow_html=True)

# ===== Sidebar Filtros =====
with st.sidebar:
    st.header("🔎 Filtros")
    q = st.text_input("Buscar (nome, responsável, tel, email, diagnóstico)", "")
    status_opt = ["(Todos)","Ativo","Pausa","Alta"]
    sel_status = st.selectbox("Status", status_opt, index=0)
    prio_opt = ["(Todas)","Normal","Alta","Urgente"]
    sel_prio = st.selectbox("Prioridade", prio_opt, index=0)

# ===== KPIs =====
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f'<div class="kpi-card"><div class="kpi-title">Total</div><div class="kpi-value">{len(df)}</div></div>', unsafe_allow_html=True)
with c2: st.markdown(f'<div class="kpi-card"><div class="kpi-title">Ativos</div><div class="kpi-value">{int((df["Status"]=="Ativo").sum())}</div></div>', unsafe_allow_html=True)
with c3: st.markdown(f'<div class="kpi-card"><div class="kpi-title">Pausa</div><div class="kpi-value">{int((df["Status"]=="Pausa").sum())}</div></div>', unsafe_allow_html=True)
with c4: st.markdown(f'<div class="kpi-card"><div class="kpi-title">Altas</div><div class="kpi-value">{int((df["Status"]=="Alta").sum())}</div></div>', unsafe_allow_html=True)

# ===== Aplicar filtros para a lista/grade =====
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

# ===== Ações topo =====
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
            st.warning("Informe um telefone válido.")
with ac3:
    st.caption("Use o editor focado para alterar e notificar no Telegram.")
st.markdown('</div>', unsafe_allow_html=True)

# ===== Lista (somente leitura) + Detalhes rápidos =====
st.subheader("🔍 Detalhes rápidos")
if df_view.empty:
    st.caption("Nenhum paciente nos filtros atuais.")
else:
    for _, row in df_view.iterrows():
        nome = str(row.get("Nome","")).strip() or "(sem nome)"
        status = str(row.get("Status","")).strip() or "-"
        prio = str(row.get("Prioridade","")).strip() or "-"
        with st.expander(f"{nome} — {status} • {prio}"):
            cimg, cinfo = st.columns([1,3])
            with cimg:
                foto = (row.get("FotoURL") or "").strip()
                if foto:
                    try: st.image(foto, use_container_width=True)
                    except Exception: st.caption("Não foi possível carregar a imagem.")
                else:
                    st.caption("Sem foto")
            with cinfo:
                st.markdown(f"**PacienteID:** {row['PacienteID']}")
                st.markdown(f"**Responsável:** {row.get('Responsavel') or '—'}")
                st.markdown(f"**Telefone:** {row.get('Telefone') or '—'}")
                st.markdown(f"**Email:** {row.get('Email') or '—'}")
                st.markdown(f"**Nascimento:** {row.get('DataNascimento') or '—'}")
                st.markdown(f"**Convênio:** {row.get('Convenio') or '—'}")
                st.markdown(f"**Diagnóstico:** {row.get('Diagnostico') or '—'}")
                st.markdown(f"**Observações:** {row.get('Observacoes') or '—'}")

# ===== Editor focado (busca + editar 1 paciente) =====
st.markdown("---")
st.subheader("✏️ Editor focado (com Telegram)")

q_edit = st.text_input("Buscar paciente (nome, responsável, tel, email, diagnóstico)", key="busca_editor").strip().lower()
df_edit = df.copy()
if q_edit:
    mask = (
        df_edit["Nome"].str.lower().str.contains(q_edit, na=False) |
        df_edit["Responsavel"].str.lower().str.contains(q_edit, na=False) |
        df_edit["Telefone"].str.lower().str.contains(q_edit, na=False) |
        df_edit["Email"].str.lower().str.contains(q_edit, na=False) |
        df_edit["Diagnostico"].str.lower().str.contains(q_edit, na=False)
    )
    df_edit = df_edit[mask]
opts = [f"{row['Nome']} — {row['PacienteID']}" for _, row in df_edit.sort_values("Nome").iterrows()]
sel_label = st.selectbox("Escolha o paciente", ["(selecione)"] + opts, index=0)

if sel_label != "(selecione)":
    sel_pid = sel_label.rsplit("—", 1)[-1].strip()
    rec_old = df[df["PacienteID"]==sel_pid].iloc[0].to_dict()

    with st.expander("Editar cadastro", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nome_e = st.text_input("Nome*", rec_old.get("Nome",""))
            nasc_e = st.text_input("Nascimento (DD/MM/AAAA)", rec_old.get("DataNascimento",""))
            resp_e = st.text_input("Responsável", rec_old.get("Responsavel",""))
            tel_e  = st.text_input("Telefone", rec_old.get("Telefone",""))
            email_e= st.text_input("Email", rec_old.get("Email",""))
            conv_e = st.text_input("Convênio (ou 'Particular')", rec_old.get("Convenio",""))
        with c2:
            diag_e = st.text_area("Diagnóstico(s)", rec_old.get("Diagnostico",""))
            status_e = st.selectbox("Status", ["Ativo","Pausa","Alta"], index=["Ativo","Pausa","Alta"].index(rec_old.get("Status","Ativo")) if rec_old.get("Status","Ativo") in ["Ativo","Pausa","Alta"] else 0)
            prio_e   = st.selectbox("Prioridade", ["Normal","Alta","Urgente"], index=["Normal","Alta","Urgente"].index(rec_old.get("Prioridade","Normal")) if rec_old.get("Prioridade","Normal") in ["Normal","Alta","Urgente"] else 0)
            foto_e = st.text_input("FotoURL (Drive/Cloudinary)", rec_old.get("FotoURL",""))
            obs_e  = st.text_area("Observações", rec_old.get("Observacoes",""))

        if st.button("💾 Salvar edição e notificar", type="primary", use_container_width=True, key="btn_save_edit"):
            if not nome_e.strip():
                st.error("Informe o nome do paciente.")
            else:
                try:
                    rec_new = {
                        "PacienteID": rec_old["PacienteID"],
                        "Nome": nome_e.strip(),
                        "DataNascimento": _to_date_str(nasc_e),
                        "Responsavel": (resp_e or "").strip(),
                        "Telefone": (tel_e or "").strip(),
                        "Email": (email_e or "").strip(),
                        "Diagnostico": (diag_e or "").strip(),
                        "Convenio": (conv_e or "").strip() or "Particular",
                        "Status": status_e,
                        "Prioridade": prio_e,
                        "FotoURL": (foto_e or "").strip(),
                        "Observacoes": (obs_e or "").strip()
                    }
                    diffs = _diff_changes(rec_old, rec_new)

                    df_aplica = df.copy()
                    idx = df_aplica.index[df_aplica["PacienteID"]==rec_new["PacienteID"]][0]
                    for k,v in rec_new.items():
                        df_aplica.at[idx, k] = v
                    out = df_aplica[PAC_COLS].fillna("")
                    ws.update("A1", [PAC_COLS] + out.values.tolist())

                    _tg_card_paciente("Editado", rec_new, diffs)
                    st.success("Paciente atualizado e Telegram notificado ✅")
                    st.cache_data.clear()
                    st.rerun()
                except APIError as e:
                    _render_perm_help(e)
                    st.error("Erro do Google Sheets ao salvar.")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

# ===== Cadastro — Novo paciente (com Telegram) =====
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

                _tg_card_paciente("Novo", record, diffs=None)
                st.success(f"Paciente cadastrado e notificado ✅ ({pid})")
                st.cache_data.clear()
                st.rerun()
            except APIError as e:
                _render_perm_help(e)
                st.error("Erro do Google Sheets ao salvar novo paciente.")
            except Exception as e:
                st.error(f"Erro ao salvar novo paciente: {e}")
