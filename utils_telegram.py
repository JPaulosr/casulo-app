# utils_telegram.py
import requests
import streamlit as st

def _token() -> str | None:
    tok = (st.secrets.get("TELEGRAM_TOKEN") or "").strip()
    return tok or None

def default_chat_id() -> str:
    return (st.secrets.get("TELEGRAM_CHAT_ID_CASULO") or "-1002760402999").strip()

def tg_ready() -> bool:
    return bool(_token())

def tg_send_text(text: str, chat_id: str | None = None) -> tuple[bool, str]:
    tok = _token()
    if not tok:
        return False, "TELEGRAM_TOKEN ausente em secrets."
    chat_id = chat_id or default_chat_id()
    try:
        url = f"https://api.telegram.org/bot{tok}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=30)
        ok = r.ok and r.json().get("ok")
        return bool(ok), ("" if ok else r.text)
    except Exception as e:
        return False, str(e)

def tg_send_document(data: bytes, filename: str, mime: str = "application/octet-stream",
                     caption: str = "", chat_id: str | None = None) -> tuple[bool, str]:
    tok = _token()
    if not tok:
        return False, "TELEGRAM_TOKEN ausente em secrets."
    chat_id = chat_id or default_chat_id()
    try:
        url = f"https://api.telegram.org/bot{tok}/sendDocument"
        files = {"document": (filename, data, mime)}
        data_form = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        r = requests.post(url, data=data_form, files=files, timeout=60)
        ok = r.ok and r.json().get("ok")
        return bool(ok), ("" if ok else r.text)
    except Exception as e:
        return False, str(e)
