# pages/02_Paciente_Detalhe.py
# -*- coding: utf-8 -*-
import base64
import requests
from datetime import datetime
import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import APIError

from utils_casulo import connect, read_ws
from utils_telegram import _token as tg_token, default_chat_id as tg_default_chat_id, tg_send_text

st.set_page_config(page_title="Casulo — Paciente", page_icon="📄", layout="wide")
st.title("📄 Detalhe do Paciente")

PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"
]

LOGO_FALLBACK_URL = ""  # opcional; ou defina secrets["TELEGRAM_LOGO_FALLBACK"]

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

def _fmt_html(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _photo_or_logo(p: dict) -> str:
    foto = str(p.get("FotoURL","") or "").strip()
    if foto:
        return foto
    try:
        logo_secret = (st.secrets.get("TELEGRAM_LOGO_FALLBACK","") or "").strip()
    except Exception:
        logo_secret = ""
    return foto or logo_secret or LOGO_FALLBACK_URL or ""

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

def _card_caption(action: str, p: dict, diffs=None) -> str:
    nome = p.get("Nome") or "(sem nome)"
    pid  = p.get("PacienteID") or "-"
    status = p.get("Status") or "-"
    prio   = p.get("Prioridade") or "-"
    linhas = []
    if diffs:
        linhas.append("<b>Atualizações</b>:")
        for campo, antes, depois in diffs:
            linhas.append(f"• <b>{_fmt_html(campo)}:</b> {_fmt_html(antes)} → <code>{_fmt_html(depois)}</code>")
    caption = (
        f"<b>Paciente {action}</b>\n"
        f"<b>{_fmt_html(nome)}</b>  <i>({pid})</i>\n"
        f"Status: <b>{_fmt_html(status)}</b> • Prioridade: <b>{_fmt_html(prio)}</b>\n\n"
        + ("\n".join(linhas) if linhas else "")
    )
    return caption

# ===== Conexão =====
ss = connect()
try:
    df, ws = read_ws(ss, "Pacientes", PAC_COLS)
    df = df.reindex(columns=PAC_COLS).fillna("")
except Exception as e:
    st.error(f"Erro ao ler Pacientes: {e}")
    st.stop()

# ===== Seleção do paciente (buscável) =====
q = st.text_input("Buscar (nome, tel, diagnóstico, responsável, e-mail)").strip().lower()
df_sel = df.copy()
if q:
    m = (
        df_sel["Nome"].str.lower().str.contains(q, na=False) |
        df_sel["Telefone"].str.lower().str.contains(q, na=False) |
        df_sel["Diagnostico"].str.lower().str.contains(q, na=False) |
        df_sel["Responsavel"].str.lower().str.contains(q, na=False) |
        df_sel["Email"].str.lower().str.contains(q, na=False)
    )
    df_sel = df_sel[m]

opts = [f"{r['Nome']} — {r['PacienteID']}" for _, r in df_sel.sort_values("Nome").iterrows()]
choice = st.selectbox("Escolha o paciente", ["(selecione)"] + opts, index=0)

if choice == "(selecione)":
    st.info("Use a busca acima para localizar um paciente e visualizar/editar.")
    st.stop()

pid = choice.rsplit("—", 1)[-1].strip()
rec = df[df["PacienteID"]==pid].iloc[0].to_dict()

# ===== Card de visualização =====
col1, col2 = st.columns([1,2])
with col1:
    foto = (rec.get("FotoURL") or "").strip()
    if foto:
        try:
            st.image(foto, use_container_width=True)
        except Exception:
            st.caption("Não foi possível carregar a imagem.")
    else:
        st.caption("Sem foto")
with col2:
    st.subheader(rec.get("Nome") or "(sem nome)")
    st.markdown(f"**PacienteID:** {rec.get('PacienteID')}")
    st.markdown(f"**Status:** {rec.get('Status') or '—'}  •  **Prioridade:** {rec.get('Prioridade') or '—'}")
    st.markdown(f"**Nascimento:** {rec.get('DataNascimento') or '—'}")
    st.markdown(f"**Responsável:** {rec.get('Responsavel') or '—'}")
    st.markdown(f"**Telefone:** {rec.get('Telefone') or '—'}")
    st.markdown(f"**Email:** {rec.get('Email') or '—'}")
    st.markdown(f"**Convênio:** {rec.get('Convenio') or '—'}")
    st.markdown(f"**Diagnóstico:** {rec.get('Diagnostico') or '—'}")
    st.markdown(f"**Observações:** {rec.get('Observacoes') or '—'}")

st.markdown("---")

# ===== Editor =====
st.subheader("✏️ Editar cadastro (com Telegram)")
c1, c2 = st.columns(2)
with c1:
    nome_e = st.text_input("Nome*", rec.get("Nome",""))
    nasc_e = st.text_input("Nascimento (DD/MM/AAAA)", rec.get("DataNascimento",""))
    resp_e = st.text_input("Responsável", rec.get("Responsavel",""))
    tel_e  = st.text_input("Telefone", rec.get("Telefone",""))
    email_e= st.text_input("Email", rec.get("Email",""))
    conv_e = st.text_input("Convênio (ou 'Particular')", rec.get("Convenio",""))
with c2:
    diag_e = st.text_area("Diagnóstico(s)", rec.get("Diagnostico",""))
    status_e = st.selectbox("Status", ["Ativo","Pausa","Alta"], index=["Ativo","Pausa","Alta"].index(rec.get("Status","Ativo")) if rec.get("Status","Ativo") in ["Ativo","Pausa","Alta"] else 0)
    prio_e   = st.selectbox("Prioridade", ["Normal","Alta","Urgente"], index=["Normal","Alta","Urgente"].index(rec.get("Prioridade","Normal")) if rec.get("Prioridade","Normal") in ["Normal","Alta","Urgente"] else 0)
    foto_e = st.text_input("FotoURL (Drive/Cloudinary)", rec.get("FotoURL",""))
    obs_e  = st.text_area("Observações", rec.get("Observacoes",""))

if st.button("💾 Salvar alterações e notificar", type="primary"):
    if not nome_e.strip():
        st.error("Informe o nome do paciente.")
    else:
        try:
            new_rec = {
                "PacienteID": rec["PacienteID"],
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
            diffs = _diff_changes(rec, new_rec)

            # aplica no df e grava
            df_apply = df.copy()
            idx = df_apply.index[df_apply["PacienteID"]==new_rec["PacienteID"]][0]
            for k,v in new_rec.items():
                df_apply.at[idx, k] = v
            out = df_apply[PAC_COLS].fillna("")
            # atualiza a planilha inteira (mantém consistência)
            ws.update("A1", [PAC_COLS] + out.values.tolist())

            caption = _card_caption("Editado", new_rec, diffs)
            _tg_send_photo_card(caption, _photo_or_logo(new_rec))

            st.success("Paciente atualizado e Telegram notificado ✅")
            st.cache_data.clear()
            st.experimental_rerun()
        except APIError as e:
            st.error("Erro do Google Sheets ao salvar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
