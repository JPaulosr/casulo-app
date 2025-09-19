# === NOTIFICAÇÃO TELEGRAM (usa exclusivamente utils_telegram) ===
from utils_telegram import tg_ready, default_chat_id, tg_send_text
import requests

LOGO_FALLBACK_URL = ""  # opcional; deixe vazio e use st.secrets["TELEGRAM_LOGO_FALLBACK"] se preferir

def _photo_or_logo(p: dict) -> str:
    foto = str(p.get("FotoURL","") or "").strip()
    if foto:
        return foto
    # tenta secrets; se não houver, usa constante
    logo = ""
    try:
        logo = (st.secrets.get("TELEGRAM_LOGO_FALLBACK","") or "").strip()
    except Exception:
        pass
    return logo or LOGO_FALLBACK_URL or ""

def _fmt_html(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _send_tg_photo_or_text(caption_html: str, photo_url: str | None):
    """
    Envia foto+caption se houver photo_url; senão envia texto.
    Usa exclusivamente utils_telegram (que já lê TELEGRAM_TOKEN e chat_id padrão).
    """
    if not tg_ready():
        st.warning("⚠️ Telegram não configurado: defina TELEGRAM_TOKEN em secrets.")
        return
    chat_id = default_chat_id()
    try:
        if photo_url:
            # usa o mesmo token do utils_telegram, mas sem reimplementar auth:
            # como o util não expõe o token, fazemos fallback: se sendPhoto falhar, caímos no texto.
            # Monta URL com o token presente em st.secrets (igual ao utils_telegram)
            tok = (st.secrets.get("TELEGRAM_TOKEN") or "").strip()
            if not tok:
                ok, err = tg_send_text(caption_html, chat_id)
                if not ok:
                    st.warning(f"⚠️ Telegram (texto) falhou: {err}")
                else:
                    st.toast("Notificação enviada ao Telegram ✅", icon="✅")
                return
            url = f"https://api.telegram.org/bot{tok}/sendPhoto"
            data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML", "disable_web_page_preview": True, "photo": photo_url}
            r = requests.post(url, data=data, timeout=30)
            if r.ok and r.json().get("ok"):
                st.toast("Notificação enviada ao Telegram ✅", icon="✅")
            else:
                # fallback: manda como texto
                ok, err = tg_send_text(caption_html, chat_id)
                if not ok:
                    st.warning(f"⚠️ Telegram (texto) falhou: {err}")
        else:
            ok, err = tg_send_text(caption_html, chat_id)
            if not ok:
                st.warning(f"⚠️ Telegram (texto) falhou: {err}")
            else:
                st.toast("Notificação enviada ao Telegram ✅", icon="✅")
    except Exception as e:
        st.warning(f"⚠️ Falha ao enviar para o Telegram: {e}")

def _caption_paciente(action: str, p: dict, diffs: list[tuple[str,str,str]] | None = None) -> str:
    # action: "Novo" ou "Editado"
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

    return (
        f"<b>Paciente {action}</b>\n"
        f"<b>{_fmt_html(nome)}</b>  <i>({pid})</i>\n"
        f"Status: <b>{_fmt_html(status)}</b> • Prioridade: <b>{_fmt_html(prio)}</b>\n\n"
        + "\n".join(linhas)
    )
