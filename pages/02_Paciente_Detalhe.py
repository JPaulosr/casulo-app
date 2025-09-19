# pages/02_Paciente_Detalhe.py
import io
import requests
from datetime import datetime, date
import pandas as pd
import streamlit as st

from utils_casulo import connect, read_ws, append_rows, new_id  # usa o appender SEGURO

# =========================
# Config & constantes
# =========================
st.set_page_config(page_title="Casulo — Paciente", page_icon="📄", layout="wide")
st.title("📄 Detalhe do Paciente")

# Telegram (usa secrets e cai para as constantes abaixo, se não houver)
TELEGRAM_TOKEN_FALLBACK = "8257359388:AAGayJElTPT0pQadtamVf8LoL7R6EfWzFGE"
TELEGRAM_CHATID_FALLBACK = "-1002760402999"  # seu canal

def _tg_token():
    try:
        tok = st.secrets.get("TELEGRAM_TOKEN", "").strip()
        return tok or TELEGRAM_TOKEN_FALLBACK
    except Exception:
        return TELEGRAM_TOKEN_FALLBACK

def _tg_chat_id():
    try:
        cid = st.secrets.get("TELEGRAM_CHAT_ID", "").strip()
        return cid or TELEGRAM_CHATID_FALLBACK
    except Exception:
        return TELEGRAM_CHATID_FALLBACK

def tg_send_pdf(file_bytes: bytes, filename: str, caption: str = "") -> tuple[bool,str]:
    token = _tg_token()
    chat_id = _tg_chat_id()
    if not token or not chat_id:
        return False, "TELEGRAM_TOKEN ou CHAT_ID ausente."
    try:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {"document": (filename, file_bytes, "application/pdf")}
        data = {"chat_id": chat_id, "caption": caption}
        r = requests.post(url, data=data, files=files, timeout=60)
        ok = (r.status_code == 200 and r.json().get("ok"))
        return (ok, "" if ok else r.text)
    except Exception as e:
        return False, str(e)

# =========================
# Helpers de parsing/format
# =========================
DATA_FMT = "%d/%m/%Y"

def to_date(s):
    if s is None: return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def brl(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

# =========================
# Leitura das planilhas
# =========================
ss = connect()

PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]

SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim",
            "Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]

PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido",
            "TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

# Relatórios do paciente
REL_COLS = ["RelatorioID","PacienteID","Data","Tipo","Titulo","Autor","Texto","ArquivoURL"]

df_pac, _ = read_ws(ss, "Pacientes",  PAC_COLS)
df_ses, _ = read_ws(ss, "Sessoes",    SES_COLS)
df_pag, _ = read_ws(ss, "Pagamentos", PAG_COLS)
df_rel, ws_rel = read_ws(ss, "Relatorios", REL_COLS)  # cria se não existe

# =========================
# Selecionar paciente por nome
# =========================
nomes = [""] + sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
nome_sel = st.selectbox("Paciente", nomes, index=0)

if not nome_sel:
    st.info("Selecione um paciente pelo nome.")
    st.stop()

p_row = df_pac[df_pac["Nome"].astype(str).str.strip() == nome_sel].head(1)
if p_row.empty:
    st.warning("Paciente não encontrado.")
    st.stop()

p = p_row.iloc[0]
pid = str(p["PacienteID"])

# =========================
# Header — foto + dados
# =========================
col1, col2 = st.columns([1,3])
with col1:
    foto = str(p.get("FotoURL","")).strip()
    if foto:
        st.image(foto, caption=p.get("Nome",""), width=260)
with col2:
    st.markdown(f"## {p.get('Nome','')}")
    st.write(f"**Responsável:** {p.get('Responsavel','-')}  |  **Telefone:** {p.get('Telefone','-')}")
    st.write(f"**Diagnóstico:** {p.get('Diagnostico','-')}")
    st.write(f"**Convênio:** {p.get('Convenio','-')}  |  **Status:** {p.get('Status','-')}  |  **Prioridade:** {p.get('Prioridade','-')}")
    st.caption(f"ID interno: {pid}")

st.divider()

# =========================
# KPIs do paciente
# =========================
df_ses_p = df_ses[df_ses["PacienteID"].astype(str) == pid].copy()
df_pag_p = df_pag[df_pag["PacienteID"].astype(str) == pid].copy()
df_rel_p = df_rel[df_rel["PacienteID"].astype(str) == pid].copy()

df_ses_p["__dt"] = df_ses_p.get("Data","").apply(to_date)
df_pag_p["__dt"] = df_pag_p.get("Data","").apply(to_date)
df_pag_p["__liq"] = pd.to_numeric(df_pag_p.get("Liquido",0), errors="coerce").fillna(0)

total_sessoes = int(len(df_ses_p))
realizadas = int((df_ses_p.get("Status","").astype(str).str.lower() == "realizada").sum())
recebido_liq = float(df_pag_p["__liq"].sum())
qtd_relatorios = int(len(df_rel_p))
ultima_sessao = df_ses_p["__dt"].dropna().max() if not df_ses_p.empty else None

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Sessões", total_sessoes)
k2.metric("Realizadas", realizadas)
k3.metric("Recebido (líquido)", brl(recebido_liq))
k4.metric("Relatórios", qtd_relatorios)
k5.metric("Última sessão", ultima_sessao.strftime(DATA_FMT) if ultima_sessao else "-")

# =========================
# Abas
# =========================
tab_visao, tab_rel, tab_ses, tab_fin, tab_docs = st.tabs(
    ["👁️ Visão geral","📄 Relatórios","📝 Sessões","💰 Financeiro","📎 Documentos"]
)

# ---------- Visão geral: Linha do tempo (com expanders e ordem crescente) ----------
with tab_visao:
    st.subheader("Linha do tempo")

    # ordena por data ASC, e por hora também
    df_ses_p["__ord_h"] = pd.to_datetime(df_ses_p.get("HoraInicio",""), format="%H:%M", errors="coerce")
    df_ses_p = df_ses_p.sort_values(["__dt","__ord_h"], ascending=[True, True])

    # contadores
    s_status = df_ses_p.get("Status","").astype(str).str.lower()
    n_ag = int(s_status.isin(["agendada","confirmada"]).sum())
    n_re = int((s_status == "realizada").sum())
    n_fa = int((s_status == "falta").sum())
    n_ca = int((s_status == "cancelada").sum())

    st.caption(f"Últimas {min(40, len(df_ses_p))} sessões · Agendadas/Confirmadas: {n_ag} · Realizadas: {n_re} · Faltas: {n_fa} · Canceladas: {n_ca}")

    blocos = {
        "Agendadas/Confirmadas": df_ses_p[s_status.isin(["agendada","confirmada"])],
        "Realizadas": df_ses_p[s_status == "realizada"],
        "Faltas": df_ses_p[s_status == "falta"],
        "Canceladas": df_ses_p[s_status == "cancelada"],
    }

    for titulo, bloco in blocos.items():
        with st.expander(f"{titulo} ({len(bloco)})", expanded=(titulo=="Agendadas/Confirmadas")):
            if bloco.empty:
                st.info("Nada aqui.")
            else:
                for d, grupo in bloco.groupby("__dt"):
                    st.markdown(f"**{d.strftime(DATA_FMT)} — Sessão**")
                    for _, r in grupo.iterrows():
                        hi = str(r.get("HoraInicio","") or "").strip()
                        hf = str(r.get("HoraFim","") or "").strip()
                        prof = str(r.get("Profissional","") or "")
                        tipo = str(r.get("Tipo","Terapia") or "Terapia")
                        st.markdown(f"**{tipo}**  \n{hi}{('–'+hf) if hf else ''} · {prof}")

# ---------- Relatórios ----------
with tab_rel:
    st.subheader("Relatórios do paciente")

    # Filtros
    colf1, colf2, colf3 = st.columns([1,1,2])
    tipos = ["(todos)"] + sorted(df_rel_p.get("Tipo","").astype(str).str.strip().unique().tolist())
    with colf1:
        tipo_f = st.selectbox("Tipo", tipos, index=0)
    with colf2:
        de = st.date_input("De", value=None)
    with colf3:
        ate = st.date_input("Até", value=None)

    rel_vis = df_rel_p.copy()
    rel_vis["__dt"] = rel_vis.get("Data","").apply(to_date)
    if tipo_f != "(todos)":
        rel_vis = rel_vis[rel_vis.get("Tipo","").astype(str) == tipo_f]
    if de:
        rel_vis = rel_vis[rel_vis["__dt"] >= de]
    if ate:
        rel_vis = rel_vis[rel_vis["__dt"] <= ate]

    rel_vis = rel_vis.sort_values("__dt", ascending=True)

    # Lista compacta + seleção
    opts = []
    labels = {}
    for _, r in rel_vis.iterrows():
        rid = str(r.get("RelatorioID",""))
        data_txt = r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-"
        titulo = str(r.get("Titulo","")).strip() or "(sem título)"
        lbl = f"🗂️ {data_txt} — {str(r.get('Tipo','')).strip() or '-'} · {titulo}"
        opts.append(rid)
        labels[rid] = lbl

    sel = st.multiselect("Selecionar relatórios para exportar", opts, format_func=lambda x: labels.get(x, x))

    colbtn1, colbtn2, colbtn3, colbtn4 = st.columns([1,1,1,2])
    with colbtn1:
        md_ok = st.button("⬇️ MD", use_container_width=True)
    with colbtn2:
        pdf_ok = st.button("⬇️ PDF", use_container_width=True)
    with colbtn3:
        docx_ok = st.button("⬇️ DOCX", use_container_width=True)
    with colbtn4:
        tg_ok = st.button("📤 Enviar PDF ao Telegram", use_container_width=True)

    # Funções de export simples (PDF com reportlab se existir)
    def _compose_md(rows: pd.DataFrame) -> str:
        parts = []
        for _, r in rows.iterrows():
            dtxt = (r["__dt"].strftime(DATA_FMT) if pd.notna(r["__dt"]) else "-")
            parts += [
                f"# {r.get('Titulo','(sem título)')}",
                f"*Data:* {dtxt}  ",
                f"*Tipo:* {r.get('Tipo','-')}  ",
                f"*Autor:* {r.get('Autor','-')}  ",
                "",
                str(r.get("Texto","")).strip(),
                "",
                ("Link: " + str(r.get("ArquivoURL","")).strip()) if str(r.get("ArquivoURL","")).strip() else "",
                "\n---\n"
            ]
        return "\n".join([p for p in parts if p is not None])

    rows_sel = rel_vis[rel_vis["RelatorioID"].astype(str).isin(sel)].copy()

    if md_ok:
        if rows_sel.empty:
            st.warning("Selecione ao menos um relatório.")
        else:
            md_txt = _compose_md(rows_sel)
            st.download_button("Baixar .md", data=md_txt.encode("utf-8"), file_name=f"relatorios_{pid}.md")

    if pdf_ok or tg_ok:
        if rows_sel.empty:
            st.warning("Selecione ao menos um relatório.")
        else:
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import cm
                buf = io.BytesIO()
                c = canvas.Canvas(buf, pagesize=A4)
                W, H = A4
                y0 = H - 2*cm
                for _, r in rows_sel.iterrows():
                    c.setFont("Helvetica-Bold", 12)
                    title = (str(r.get("Titulo","")) or "(sem título)")[:90]
                    c.drawString(2*cm, y0, title)
                    y = y0 - 0.6*cm
                    c.setFont("Helvetica", 10)
                    meta = f"{(r['__dt'].strftime(DATA_FMT) if pd.notna(r['__dt']) else '-') } • {str(r.get('Tipo','-'))} • {str(r.get('Autor','-'))}"
                    c.drawString(2*cm, y, meta)
                    y -= 0.6*cm
                    for line in str(r.get("Texto","")).splitlines():
                        for chunk in [line[i:i+100] for i in range(0, len(line), 100)]:
                            if y < 2*cm:
                                c.showPage(); y = H - 2*cm
                            c.drawString(2*cm, y, chunk); y -= 0.5*cm
                    url = str(r.get("ArquivoURL","")).strip()
                    if url:
                        if y < 2*cm: c.showPage(); y = H - 2*cm
                        c.setFillColorRGB(0,0,1); c.drawString(2*cm, y, f"Link: {url}"); c.setFillColorRGB(0,0,0)
                        y -= 0.6*cm
                    c.showPage()
                c.save()
                pdf_bytes = buf.getvalue()
                buf.close()
                if pdf_ok:
                    st.download_button("Baixar PDF", data=pdf_bytes, file_name=f"relatorios_{pid}.pdf")
                if tg_ok:
                    ok, err = tg_send_pdf(pdf_bytes, f"relatorios_{pid}.pdf", caption=f"Relatórios de {nome_sel}")
                    if ok:
                        st.success("Enviado ao Telegram ✅")
                    else:
                        st.error(f"Falhou ao enviar: {err}")
            except ImportError:
                st.error("Faltou a dependência `reportlab` para gerar PDF.")

    if docx_ok:
        if rows_sel.empty:
            st.warning("Selecione ao menos um relatório.")
        else:
            try:
                from docx import Document
                doc = Document()
                for _, r in rows_sel.iterrows():
                    doc.add_heading(str(r.get("Titulo","(sem título)")), 1)
                    meta = f"{(r['__dt'].strftime(DATA_FMT) if pd.notna(r['__dt']) else '-') } • {str(r.get('Tipo','-'))} • {str(r.get('Autor','-'))}"
                    doc.add_paragraph(meta)
                    doc.add_paragraph(str(r.get("Texto","")))
                    url = str(r.get("ArquivoURL","")).strip()
                    if url:
                        doc.add_paragraph(f"Link: {url}")
                    doc.add_page_break()
                buf = io.BytesIO()
                doc.save(buf)
                st.download_button("Baixar DOCX", data=buf.getvalue(), file_name=f"relatorios_{pid}.docx")
            except ImportError:
                st.error("Faltou a dependência `python-docx` para gerar DOCX.")

    st.markdown("---")
    st.subheader("Novo relatório")

    # ====== Formulário de novo relatório ======
    with st.form("novo_rel"):
        c1, c2 = st.columns([2,1])
        with c1:
            titulo = st.text_input("Título", "")
        with c2:
            data_rel = st.date_input("Data", value=date.today(), format="YYYY/MM/DD")

        tipo = st.selectbox("Tipo", ["Evolução","Avaliação","Anamnese","Alta","Outro"], index=0)
        autor = st.text_input("Autor", "Fernanda")   # padrão para sua clínica
        texto = st.text_area("Texto (anotações, evolução, anamnese...)", height=220)
        arq_url = st.text_input("ArquivoURL (link opcional — Drive/Cloudinary)", "")

        ok_save = st.form_submit_button("Salvar relatório")

    if ok_save:
        if not titulo.strip():
            st.error("Informe o título.")
        else:
            rid = new_id("R")
            row = {
                "RelatorioID": rid,
                "PacienteID": pid,
                "Data": data_rel.strftime(DATA_FMT),
                "Tipo": tipo,
                "Titulo": titulo.strip(),
                "Autor": autor.strip(),
                "Texto": texto.strip(),
                "ArquivoURL": arq_url.strip()
            }
            # 👇 Usa o appender seguro — evita KeyError mesmo se faltar alguma coluna
            append_rows(ws_rel, [row], default_headers=REL_COLS)
            st.success(f"Relatório salvo ({rid}).")
            st.cache_data.clear()
            st.rerun()

# ---------- Sessões ----------
with tab_ses:
    st.subheader("Sessões do paciente")
    if df_ses_p.empty:
        st.info("Sem sessões.")
    else:
        show_cols = ["Data","HoraInicio","HoraFim","Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes"]
        show_cols = [c for c in show_cols if c in df_ses_p.columns]
        df_ses_p2 = df_ses_p.sort_values(["__dt","__ord_h"], ascending=[True, True])
        st.dataframe(df_ses_p2[show_cols], use_container_width=True, hide_index=True)

# ---------- Financeiro ----------
with tab_fin:
    st.subheader("Financeiro (recebido)")
    if df_pag_p.empty:
        st.info("Sem pagamentos.")
    else:
        show_cols = ["Data","Forma","Bruto","Liquido","TaxaValor","Referencia","Obs"]
        show_cols = [c for c in show_cols if c in df_pag_p.columns]
        st.dataframe(df_pag_p.sort_values("__dt")[show_cols], use_container_width=True, hide_index=True)
        st.metric("Total líquido deste paciente", brl(float(df_pag_p['__liq'].sum())))

# ---------- Documentos ----------
with tab_docs:
    st.subheader("Documentos & anexos")
    st.info("Para anexar um link/arquivo, use o campo **ArquivoURL** ao criar um Relatório acima.\n\n"
            "Se preferir uma aba dedicada 'Documentos' na planilha (ex.: colunas: PacienteID, Titulo, Data, URL, Obs), dá pra adicionar depois.")
    # Mostra os relatórios com link:
    rel_com_link = df_rel_p[df_rel_p.get("ArquivoURL","").astype(str).str.strip() != ""].copy()
    if rel_com_link.empty:
        st.caption("Nenhum link anexado ainda (ArquivoURL está vazio nos relatórios).")
    else:
        rel_com_link["__dt"] = rel_com_link.get("Data","").apply(to_date)
        rel_com_link = rel_com_link.sort_values("__dt")
        for _, r in rel_com_link.iterrows():
            dtxt = (to_date(r.get("Data")).strftime(DATA_FMT) if to_date(r.get("Data")) else "-")
            st.markdown(f"- **{dtxt}** — {r.get('Titulo','(sem título)')} · [{r.get('ArquivoURL')}]({r.get('ArquivoURL')})")
