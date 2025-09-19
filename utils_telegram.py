# utils_telegram.py
import os
import requests
import streamlit as st

# --- Fallback via variáveis de ambiente ---
TELEGRAM_TOKEN_FALLBACK = (
    os.getenv("TELEGRAM_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
).strip()

TELEGRAM_CHATID_FALLBACK = (
    os.getenv("TELEGRAM_CHAT_ID", "")
    or os.getenv("TELEGRAM_CHAT_ID_CASULO", "")
    or os.getenv("TELEGRAM_CHAT_ID_PADRAO", "")
).strip()

_TELEGRAM_KEY_CANDIDATES = ("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN")
_CHATID_KEY_CANDIDATES = ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_CASULO", "TELEGRAM_CHAT_ID_PADRAO")

def _tg_token() -> str:
    # 1) override via UI
    ov = (st.session_state.get("TELEGRAM_TOKEN_OVERRIDE", "") or "").strip()
    if ov:
        return ov
    # 2) secrets
    try:
        for k in _TELEGRAM_KEY_CANDIDATES:
            v = (st.secrets.get(k, "") or "").strip()
            if v:
                return v
    except Exception:
        pass
    # 3) env
    return TELEGRAM_TOKEN_FALLBACK

def _tg_chat_id() -> str:
    ov = (st.session_state.get("TELEGRAM_CHAT_ID_OVERRIDE", "") or "").strip()
    if ov:
        return ov
    try:
        for k in _CHATID_KEY_CANDIDATES:
            v = (st.secrets.get(k, "") or "").strip()
            if v:
                return v
    except Exception:
        pass
    return TELEGRAM_CHATID_FALLBACK

def tg_ready() -> tuple[bool, bool, dict]:
    tok = _tg_token()
    cid = _tg_chat_id()
    info = {
        "prefer_keys_token": list(_TELEGRAM_KEY_CANDIDATES),
        "prefer_keys_chat": list(_CHATID_KEY_CANDIDATES),
        "token_source": "override" if st.session_state.get("TELEGRAM_TOKEN_OVERRIDE") else ("secrets/env" if tok else "MISSING"),
        "chat_source": "override" if st.session_state.get("TELEGRAM_CHAT_ID_OVERRIDE") else ("secrets/env" if cid else "MISSING"),
        "token_masked": (tok[:6] + "…" + tok[-4:]) if tok else "",
        "chat_id": cid,
    }
    return bool(tok), bool(cid), info

def tg_send_pdf(file_bytes: bytes, filename: str, caption: str = "") -> tuple[bool, str]:
    token_ok, chat_ok, dbg = tg_ready()
    if not (token_ok and chat_ok):
        return (
            False,
            f"Telegram indisponível. Token OK? {token_ok} | ChatID OK? {chat_ok} | "
            f"Procuradas: token {dbg['prefer_keys_token']} chat {dbg['prefer_keys_chat']}"
        )
    try:
        url = f"https://api.telegram.org/bot{_tg_token()}/sendDocument"
        files = {"document": (filename, file_bytes, "application/pdf")}
        data = {"chat_id": _tg_chat_id(), "caption": (caption or "")[:1024]}
        r = requests.post(url, data=data, files=files, timeout=60)
        ok = r.ok and r.json().get("ok")
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, f"Erro de rede: {e}"

def tg_test_message(text: str = "Teste ✅") -> tuple[bool, str]:
    token_ok, chat_ok, dbg = tg_ready()
    if not (token_ok and chat_ok):
        return False, "Token/Chat ID ausente."
    try:
        url = f"https://api.telegram.org/bot{_tg_token()}/sendMessage"
        payload = {"chat_id": _tg_chat_id(), "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=30)
        ok = r.ok and r.json().get("ok")
        return (bool(ok), "" if ok else f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return False, str(e)

def tg_debug_expander():
    """Renderiza um expander com diagnóstico + override."""
    with st.expander("🔧 Diagnóstico Telegram"):
        token_ok, chat_ok, dbg = tg_ready()
        st.write(f"Token OK? **{token_ok}** | ChatID OK? **{chat_ok}**")
        st.caption(f"Fonte token: {dbg['token_source']} | Fonte chat: {dbg['chat_source']}")
        if token_ok:
            st.caption(f"Token (mascarado): {dbg['token_masked']}")
        if chat_ok:
            st.caption(f"Chat ID: {dbg['chat_id']}")
        try:
            st.caption("Chaves disponíveis em st.secrets (somente nomes):")
            st.code(", ".join(sorted(list(st.secrets.keys()))))
        except Exception as e:
            st.caption(f"Não foi possível listar st.secrets ({e})")

        st.divider()
        st.caption("👉 Override temporário (usa sessão atual):")
        tok_in = st.text_input("Token do Bot (override temporário)", type="password",
                               value=st.session_state.get("TELEGRAM_TOKEN_OVERRIDE", ""))
        cid_in = st.text_input("Chat ID (override temporário)",
                               value=st.session_state.get("TELEGRAM_CHAT_ID_OVERRIDE", ""))
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Aplicar overrides"):
                st.session_state["TELEGRAM_TOKEN_OVERRIDE"] = (tok_in or "").strip()
                st.session_state["TELEGRAM_CHAT_ID_OVERRIDE"] = (cid_in or "").strip()
                st.success("Overrides aplicados. Agora teste o envio.")
        with col_b:
            if st.button("Testar envio de mensagem"):
                ok, err = tg_test_message("Teste ✅ (debug)")
                st.success("Mensagem enviada! ✅") if ok else st.error(f"Falhou: {err}")
