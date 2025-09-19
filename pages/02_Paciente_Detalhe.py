# pages/02_Paciente_Detalhe.py
import streamlit as st
import pandas as pd
import io, requests
from datetime import datetime

from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Paciente", page_icon="📄", layout="wide")
st.title("📄 Detalhe do Paciente")

# -------------------------- helpers --------------------------
DATA_FMT = "%d/%m/%Y"

def to_date(s):
    s = str(s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def _brl(v):
    try:
        v = float(str(v).replace(",", "."))
    except Exception:
        v = 0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

# Telegram ------------- (lê de secrets; usa canal padrão se não tiver)
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "-1002760402999").strip()

def tg_send_document(file_bytes: bytes, filename: str, caption: str) -> tuple[bool, str]:
    if not TELEGRAM_TOKEN:
        return False, "TELEGRAM_TOKEN ausente em secrets."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, file_bytes)},
            timeout=40,
        )
        ok = r.ok and r.json().get("ok")
        return (True, "Enviado.") if ok else (False, f"Telegram erro: {r.text}")
    except Exception as e:
        return False, f"Falha de rede: {e}"

# -------------------------- dados --------------------------
ss = connect()
PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional",
            "Status","Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
OBJ_COLS = ["ObjetivoID","PacienteID","Categoria","Descricao","NivelAtual(0-100)","ProximaMeta","UltimaRevisao"]
REL_COLS = ["RelatorioID","PacienteID","Data","Tipo","Titulo","Autor","CorpoMD","ArquivoURL"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

df_pac, _ = read_ws(ss, "Pacientes",  PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes",    SES_COLS)
df_obj, _ = read_ws(ss, "Objetivos",  OBJ_COLS)
df_rel, _ = read_ws(ss, "Relatorios", REL_COLS)  # se não existir, a função já cria/normaliza
df_pag, _ = read_ws(ss, "Pagamentos", PAG_COLS)

# -------------------------- escolha do paciente --------------------------
nomes = [""] + sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
nome_sel = st.selectbox("Paciente", nomes, index=0, placeholder="Digite o nome...")
if not nome_sel:
    st.info("Selecione um paciente pelo nome.")
    st.stop()

p_row = df_pac[df_pac["Nome"].astype(str).str.strip() == nome_sel].head(1)
if p_row.empty:
    st.warning("Paciente não encontrado.")
    st.stop()

p = p_row.iloc[0]
pid = str(p["PacienteID"])

# Header
col1, col2 = st.columns([1,3])
with col1:
    foto = str(p.get("FotoURL","")).strip()
    if foto:
        st.image(foto, caption=p.get("Nome",""), width=230)
with col2:
    st.markdown(f"### {p.get('Nome','')}")
    st.write(f"**Responsável:** {p.get('Responsavel','-')}  |  **Telefone:** {p.get('Telefone','-')}")
    st.write(f"**Diagnóstico:** {p.get('Diagnostico','-')}")
    st.write(f"**Convênio:** {p.get('Convenio','-')}  |  **Status:** {p.get('Status','-')}  |  **Prioridade:** {p.get('Prioridade','-')}")
    if str(p.get("Observacoes","")).strip():
        st.caption(p.get("Observacoes",""))

st.divider()

# -------------------------- métricas rápidas --------------------------
ses_p = df_ses[df_ses["PacienteID"].astype(str) == pid].copy()
ses_p["__dt"] = ses_p["Data"].apply(to_date)
ses_p = ses_p.sort_values(["__dt","HoraInicio"], ascending=[True, True])

pag_p = df_pag[df_pag["PacienteID"].astype(str) == pid].copy()
pag_p["__dt"] = pag_p["Data"].apply(to_date)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Sessões", len(ses_p))
k2.metric("Recebido (líquido)", _brl(pd.to_numeric(pag_p["Liquido"], errors="coerce").fillna(0).sum()))
ultimo = ses_p["__dt"].dropna().max() if not ses_p.empty else None
k3.metric("Relatórios", len(df_rel[df_rel["PacienteID"].astype(str) == pid]))
k4.metric("Última sessão", ultimo.strftime(DATA_FMT) if ultimo else "—")

# -------------------------- tabs --------------------------
t_visao, t_rel, t_ses, t_fin, t_docs = st.tabs(["👁️ Visão geral","📝 Relatórios","🗓️ Sessões","💰 Financeiro","📎 Documentos"])

# ============== VISÃO GERAL ==============
with t_visao:
    st.subheader("Linha do tempo")
    if ses_p.empty:
        st.info("Sem sessões registradas.")
    else:
        # contadores por status (últimas 40 para referência visual)
        ult40 = ses_p.tail(40)
        ag = (ult40["Status"].isin(["Agendada","Confirmada"])).sum()
        re = (ult40["Status"] == "Realizada").sum()
        fa = (ult40["Status"] == "Falta").sum()
        ca = (ult40["Status"] == "Cancelada").sum()
        st.caption(f"Últimas 40 sessões · Agendadas/Confirmadas: **{ag}** · Realizadas: **{re}** · Faltas: **{fa}** · Canceladas: **{ca}**")

        # expanders por grupo de status
        base_cols = ["Data","HoraInicio","HoraFim","Tipo","Profissional","Status","Observacoes"]
        base_cols = [c for c in base_cols if c in ses_p.columns]

        grp_ag = ses_p[ses_p["Status"].isin(["Agendada","Confirmada"])]
        grp_re = ses_p[ses_p["Status"].isin(["Realizada"])]
        grp_fx = ses_p[ses_p["Status"].isin(["Falta","Cancelada"])]

        with st.expander(f"Agendadas/Confirmadas ({len(grp_ag)})", expanded=True):
            _g = grp_ag.copy()
            if not _g.empty:
                _g["Data"] = _g["__dt"].apply(lambda d: d.strftime(DATA_FMT) if d else "")
                st.dataframe(_g[base_cols], use_container_width=True, hide_index=True)
            else:
                st.caption("—")

        with st.expander(f"Realizadas ({len(grp_re)})", expanded=True):
            _g = grp_re.copy()
            if not _g.empty:
                _g["Data"] = _g["__dt"].apply(lambda d: d.strftime(DATA_FMT) if d else "")
                st.dataframe(_g[base_cols], use_container_width=True, hide_index=True)
            else:
                st.caption("—")

        with st.expander(f"Faltas/Canceladas ({len(grp_fx)})", expanded=False):
            _g = grp_fx.copy()
            if not _g.empty:
                _g["Data"] = _g["__dt"].apply(lambda d: d.strftime(DATA_FMT) if d else "")
                st.dataframe(_g[base_cols], use_container_width=True, hide_index=True)
            else:
                st.caption("—")

# ============== RELATÓRIOS ==============
with t_rel:
    st.subheader("Relatórios")
    rel = df_rel[df_rel["PacienteID"].astype(str) == pid].copy()
    rel["__dt"] = rel["Data"].apply(to_date)
    rel = rel.sort_values("__dt", ascending=False)

    # labels mais fáceis de identificar
    def rel_label(row):
        d = row["__dt"].strftime(DATA_FMT) if pd.notna(row["__dt"]) else "-"
        t = str(row.get("Tipo","")).strip() or "Relatório"
        ti = str(row.get("Titulo","")).strip() or "(sem título)"
        return f"{d} — {t} · {ti}"

    ids = rel["RelatorioID"].astype(str).tolist()
    lab = [rel_label(r) for _, r in rel.iterrows()]
    sel_ids = st.multiselect("Selecionar relatórios para exportar", ids, format_func=lambda x: lab[ids.index(x)] if x in ids else x)

    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1:
        if st.button("⬇️ MD", use_container_width=True, disabled=not sel_ids):
            out = ""
            for rid in sel_ids:
                r = rel[rel["RelatorioID"].astype(str)==rid].iloc[0]
                d = r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-"
                out += f"# {r.get('Titulo','(sem título)')}\n"
                out += f"*{d} · {r.get('Tipo','Relatório')} · {r.get('Autor','-')}*\n\n"
                out += (r.get("CorpoMD","") or "") + "\n\n---\n\n"
            st.download_button("Baixar .md", data=out.encode("utf-8"), file_name=f"relatorios_{p.get('Nome','')}.md", use_container_width=True)

    # Exportar PDF/DOCX (render leve via markdown -> HTML simples)
    def build_html(md_text: str, title: str) -> str:
        # render extremamente simples (sem lib externa)
        md_text = md_text.replace("\n", "<br/>")
        return f"""
        <html><head><meta charset="utf-8"></head>
        <body style="font-family:system-ui, Segoe UI, Arial; padding:24px;">
        <h2>{title}</h2>
        {md_text}
        </body></html>
        """

    def html_to_pdf_bytes(html: str) -> bytes:
        # fallback simples: entrega HTML como .pdf fake se não houver weasy/pyppeteer
        # (Streamlit Cloud costuma não permitir binários; mantenha HTML mesmo)
        return html.encode("utf-8")

    def html_to_docx_bytes(html: str) -> bytes:
        # docx muito simples (HTML dentro) para compatibilidade básica
        return html.encode("utf-8")

    with c2:
        if st.button("📄 PDF", use_container_width=True, disabled=not sel_ids):
            html = ""
            for rid in sel_ids:
                r = rel[rel["RelatorioID"].astype(str)==rid].iloc[0]
                d = r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-"
                bloco = f"<h3>{r.get('Titulo','(sem título)')}</h3><i>{d} · {r.get('Tipo','Relatório')} · {r.get('Autor','-')}</i><hr/>{(r.get('CorpoMD','') or '').replace(chr(10), '<br/>')}"
                html += bloco + "<hr/>"
            html = build_html(html, f"Relatórios — {p.get('Nome','')}")
            pdf_bytes = html_to_pdf_bytes(html)
            st.download_button("Baixar .pdf", data=pdf_bytes, file_name=f"relatorios_{p.get('Nome','')}.pdf", use_container_width=True)

    with c3:
        if st.button("🗎 DOCX", use_container_width=True, disabled=not sel_ids):
            html = ""
            for rid in sel_ids:
                r = rel[rel["RelatorioID"].astype(str)==rid].iloc[0]
                d = r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-"
                bloco = f"<h3>{r.get('Titulo','(sem título)')}</h3><i>{d} · {r.get('Tipo','Relatório')} · {r.get('Autor','-')}</i><hr/>{(r.get('CorpoMD','') or '').replace(chr(10), '<br/>')}"
                html += bloco + "<hr/>"
            html = build_html(html, f"Relatórios — {p.get('Nome','')}")
            docx_bytes = html_to_docx_bytes(html)
            st.download_button("Baixar .docx", data=docx_bytes, file_name=f"relatorios_{p.get('Nome','')}.docx", use_container_width=True)

    with c4:
        if st.button("📤 Enviar PDF ao Telegram", use_container_width=True, disabled=not sel_ids):
            html = ""
            for rid in sel_ids:
                r = rel[rel["RelatorioID"].astype(str)==rid].iloc[0]
                d = r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-"
                bloco = f"<h3>{r.get('Titulo','(sem título)')}</h3><i>{d} · {r.get('Tipo','Relatório')} · {r.get('Autor','-')}</i><hr/>{(r.get('CorpoMD','') or '').replace(chr(10), '<br/>')}"
                html += bloco + "<hr/>"
            html = build_html(html, f"Relatórios — {p.get('Nome','')}")
            pdf_bytes = html_to_pdf_bytes(html)
            ok, msg = tg_send_document(pdf_bytes, f"Relatorios_{p.get('Nome','')}.pdf", f"Relatórios — <b>{p.get('Nome','')}</b>")
            (st.success if ok else st.error)(("Enviado ao Telegram." if ok else f"Falhou ao enviar: {msg}"))

    st.markdown("---")
    st.subheader("Novo relatório")
    with st.form("novo_rel"):
        colA, colB = st.columns([3,1])
        with colA:
            titulo = st.text_input("Título", "")
        with colB:
            data_rel = st.date_input("Data", value=datetime.today().date(), format="YYYY/MM/DD")
        tipo = st.selectbox("Tipo", ["Evolução","Avaliação","Anamnese","Encerramento","Outro"], index=0)
        autor = st.text_input("Autor", "Fernanda")
        corpo = st.text_area("Texto (anotações, evolução, anamnese...)", height=220, placeholder="Escreva aqui...")

        ok = st.form_submit_button("Salvar relatório")
        if ok:
            if not titulo.strip():
                st.error("Informe um título.")
                st.stop()
            rid = f"R-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"
            df_new = pd.DataFrame([{
                "RelatorioID": rid,
                "PacienteID": pid,
                "Data": data_rel.strftime(DATA_FMT),
                "Tipo": tipo,
                "Titulo": titulo.strip(),
                "Autor": autor.strip() or "Fernanda",
                "CorpoMD": corpo or "",
                "ArquivoURL": "",
            }])
            # usa append_rows do utils_casulo indiretamente via gspread (read_ws já garantiu aba/headers)
            # mais simples: reabrir worksheet via read_ws e ws.append_rows
            _, ws_rel = read_ws(ss, "Relatorios", REL_COLS)
            headers = ws_rel.row_values(1)
            ws_rel.append_rows(df_new[headers].values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Relatório salvo ({rid}).")
            st.cache_data.clear()
            st.rerun()

# ============== SESSÕES ==============
with t_ses:
    st.subheader("Sessões do paciente")
    if ses_p.empty:
        st.info("Sem sessões.")
    else:
        show = ses_p.copy()
        show["Data"] = show["__dt"].apply(lambda d: d.strftime(DATA_FMT) if d else "")
        cols = ["Data","HoraInicio","HoraFim","Tipo","Profissional","Status","ObjetivosTrabalhados","Observacoes"]
        cols = [c for c in cols if c in show.columns]
        st.dataframe(show[cols], use_container_width=True, hide_index=True)

# ============== FINANCEIRO ==============
with t_fin:
    st.subheader("Pagamentos do paciente")
    pag = pag_p.copy()
    if pag.empty:
        st.info("Sem pagamentos.")
    else:
        pag["Data"] = pag["__dt"].apply(lambda d: d.strftime(DATA_FMT) if d else "")
        cols = ["Data","Forma","Bruto","Liquido","TaxaValor","Referencia","Obs"]
        cols = [c for c in cols if c in pag.columns]
        st.dataframe(pag[cols], use_container_width=True, hide_index=True)
        st.metric("Total líquido", _brl(pd.to_numeric(pag["Liquido"], errors="coerce").fillna(0).sum()))

# ============== DOCUMENTOS ==============
with t_docs:
    st.info("Anexe links/arquivos na planilha (coluna ArquivoURL nos relatórios) ou use a página de Fotos.")
