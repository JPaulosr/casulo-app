# utils_telegram.py
import os, requests, streamlit as st

_TOKEN_KEYS  = ("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN")
_CHATID_KEYS = ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_CASULO", "TELEGRAM_CHAT_ID_PADRAO")

def _read_first(keys: tuple[str, ...]) -> str:
    try:
        for k in keys:
            v = (st.secrets.get(k, "") or "").strip()
            if v:
                return v
    except Exception:
        pass
    for k in keys:
        v = (os.getenv(k, "") or "").strip()
        if v:
            return v
    return ""

def tg_token() -> str: return _read_first(_TOKEN_KEYS)
def tg_chat_id() -> str: return _read_first(_CHATID_KEYS)

def tg_ready():
    tok = tg_token(); cid = tg_chat_id()
    try:
        secrets_keys = list(st.secrets.keys())
    except Exception:
        secrets_keys = []
    env_present = [k for k in (*_TOKEN_KEYS, *_CHATID_KEYS) if (os.getenv(k) or "").strip()]
    dbg = {
        "token_ok": bool(tok), "chat_ok": bool(cid),
        "token_keys_tried": list(_TOKEN_KEYS),
        "chat_keys_tried": list(_CHATID_KEYS),
        "token_masked": (tok[:6] + "…" + tok[-4:]) if tok else "",
        "chat_id": cid or "",
        "secrets_keys_available": secrets_keys,   # nomes de chaves visíveis em st.secrets
        "env_keys_present": env_present,          # chaves presentes como env var
    }
    return bool(tok), bool(cid), dbg

def tg_send_message(text: str, chat_id: str | None = None):
    token = tg_token(); chat = chat_id or tg_chat_id()
    if not token or not chat: return False, "Token/ChatID ausente"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        ok = r.ok and r.json().get("ok", False)
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, f"Erro de rede: {e}"

def tg_send_document(file_bytes: bytes, filename: str, caption: str = "", chat_id: str | None = None):
    token = tg_token(); chat = chat_id or tg_chat_id()
    if not token or not chat: return False, "Token/ChatID ausente"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                          data={"chat_id": chat, "caption": caption[:1024]},
                          files={"document": (filename, file_bytes, "application/pdf")}, timeout=60)
        ok = r.ok and r.json().get("ok", False)
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, f"Erro de rede: {e}"

def tg_diag_markdown() -> str:
    tok_ok, cid_ok, dbg = tg_ready()
    lines = [
        f"**Token OK?** {tok_ok}  |  **ChatID OK?** {cid_ok}",
        f"**Chaves buscadas (token):** `{dbg['token_keys_tried']}`",
        f"**Chaves buscadas (chat):** `{dbg['chat_keys_tried']}`",
        f"**Token (mascarado):** `{dbg['token_masked']}`",
        f"**ChatID lido:** `{dbg['chat_id']}`",
        f"**Chaves existentes em st.secrets:** `{dbg['secrets_keys_available']}`",
        f"**Chaves presentes no ambiente:** `{dbg['env_keys_present']}`",
    ]
    return "\n\n".join(lines)
