# -*- coding: utf-8 -*-
# utils_telegram.py  (Casulo)
import os
import requests
import streamlit as st

# Quais chaves vamos aceitar (secrets e/ou env). Nada hardcoded.
_TOKEN_KEYS  = ("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN")
_CHATID_KEYS = ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_CASULO", "TELEGRAM_CHAT_ID_PADRAO")

def _read_first(keys: tuple[str, ...]) -> str:
    """Lê a 1ª chave que existir (st.secrets ou env); retorna '' se nada achado."""
    # 1) secrets
    try:
        for k in keys:
            v = (st.secrets.get(k, "") or "").strip()
            if v:
                return v
    except Exception:
        pass
    # 2) env (para dev local)
    for k in keys:
        v = (os.getenv(k, "") or "").strip()
        if v:
            return v
    return ""

def tg_token() -> str:
    return _read_first(_TOKEN_KEYS)

def tg_chat_id() -> str:
    return _read_first(_CHATID_KEYS)

def tg_ready() -> tuple[bool, bool, dict]:
    tok = tg_token()
    cid = tg_chat_id()
    dbg = {
        "token_ok": bool(tok),
        "chat_ok":  bool(cid),
        "token_keys_tried": list(_TOKEN_KEYS),
        "chat_keys_tried":  list(_CHATID_KEYS),
        "token_masked": (tok[:6] + "…" + tok[-4:]) if tok else "",
        "chat_id": cid,
    }
    return bool(tok), bool(cid), dbg

def tg_send_message(text: str, chat_id: str | None = None) -> tuple[bool, str]:
    token = tg_token()
    chat  = (chat_id or tg_chat_id())
    if not token or not chat:
        return False, "Token/ChatID ausente"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        r = requests.post(url, json=payload, timeout=30)
        ok = r.ok and r.json().get("ok", False)
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, f"Erro de rede: {e}"

def tg_send_document(file_bytes: bytes, filename: str, caption: str = "", chat_id: str | None = None) -> tuple[bool, str]:
    token = tg_token()
    chat  = (chat_id or tg_chat_id())
    if not token or not chat:
        return False, "Token/ChatID ausente"
    try:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {"document": (filename, file_bytes, "application/pdf")}
        data = {"chat_id": chat, "caption": caption[:1024]}
        r = requests.post(url, data=data, files=files, timeout=60)
        ok = r.ok and r.json().get("ok", False)
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, f"Erro de rede: {e}"

def tg_diag_markdown() -> str:
    """Bloco pronto para exibir na UI de diagnóstico."""
    tok_ok, cid_ok, dbg = tg_ready()
    lines = [
        f"**Token OK?** {tok_ok}  |  **ChatID OK?** {cid_ok}",
        f"**Chaves buscadas (token):** `{dbg['token_keys_tried']}`",
        f"**Chaves buscadas (chat):** `{dbg['chat_keys_tried']}`",
        f"**Token (mascarado):** `{dbg['token_masked']}`",
        f"**ChatID lido:** `{dbg['chat_id']}`",
    ]
    return "\n\n".join(lines)
