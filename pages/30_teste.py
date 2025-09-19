# pages/02_Paciente_Detalhe.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO
from utils_casulo import connect, read_ws, append_rows, new_id

st.set_page_config(page_title="Casulo — Paciente", page_icon="📄", layout="wide")

# ---------------- CSS leve ----------------
st.markdown("""
<style>
.main .block-container { padding-top: 1rem; }
.card {
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(255,255,255,.03);
  border-radius: 14px; padding: 14px;
}
.badge {display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;}
.chip-status-ativo    { background: rgba(34,197,94,.18);  color: #86efac; }
.chip-status-inativo  { background: rgba(239,68,68,.18);  color: #fecaca; }
.chip-prio-alta       { background: rgba(250,204,21,.18); color: #fde68a; }
.chip-prio-media      { background: rgba(59,130,246,.18); color: #bfdbfe; }
.chip-prio-baixa      { background: rgba(148,163,184,.20);color: #e2e8f0; }

.timeline-item {
  border-left: 2px solid rgba(148,163,184,.35);
  padding-left: 10px; margin-left: 6px; margin-bottom: 10px;
}
.timeline-item .date { font-size: 12px; color: #94a3b8; }
.timeline-item .title { font-weight: 700; }
.small { font-size: 12px; color: #94a3b8; }
.kpi { text-align:center; border:1px dashed rgba(148,163,184,.30); border-radius: 12px; padding: 10px 6px; }
.kpi h3 { margin:0; font-size: 22px; }
.kpi .lbl { font-size: 12px; color:#94a3b8; }
</style>
""", unsafe_allow_html=True)

# ---------------- helpers ----------------
def to_date(s):
    if s is None: return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%Y/%m/%d"):
        try: return datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

def to_float(x) -> float:
    try:
        s = str(x).strip().replace("R$","").replace(" ","")
        if s.count(",")==1 and s.count(".")>=1:
            s = s.replace(".","").replace(",",".")
        else:
            s = s.replace(",",".")
        return float(s)
    except Exception:
        return 0.0

def brl(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

# ---------------- dados base ----------------
ss = connect()

PAC_COLS = ["PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
            "Diagnostico","Convenio","Status","Prioridade","FotoURL","Observacoes"]
SES_COLS = ["SessaoID","PacienteID","Data","HoraInicio","HoraFim","Profissional","Status",
            "Tipo","ObjetivosTrabalhados","Observacoes","AnexosURL"]
OBJ_COLS = ["ObjetivoID","PacienteID","Categoria","Descricao","NivelAtual(0-100)","ProximaMeta","UltimaRevisao"]
PAG_COLS = ["PagamentoID","PacienteID","Data","Forma","Bruto","Liquido","TaxaValor","TaxaPct","Referencia","Obs","ReciboURL"]

# NOVA aba de relatórios clínicos
REL_COLS = ["RelatorioID","PacienteID","Data","Tipo","Titulo","Texto","Autor","AnexosURL","Privado"]

df_pac, ws_pac = read_ws(ss, "Pacientes",  PAC_COLS)
df_ses, _      = read_ws(ss, "Sessoes",    SES_COLS)
df_obj, _      = read_ws(ss, "Objetivos",  OBJ_COLS)
df_pag, _      = read_ws(ss, "Pagamentos", PAG_COLS)
df_rel, ws_rel = read_ws(ss, "Relatorios", REL_COLS)  # <- criada se não existir

# ---------------- seleção por nome ----------------
st.title("📄 Detalhe do Paciente")
nomes = [""] + sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
nome_sel = st.selectbox("Paciente", nomes, index=0, placeholder="Digite para buscar...")

if not nome_sel:
    st.info("Selecione um paciente pelo nome.")
    st.stop()

p_row = df_pac[df_pac["Nome"].astype(str).str.strip() == nome_sel].head(1)
if p_row.empty:
    st.warning("Paciente não encontrado.")
    st.stop()

p = p_row.iloc[0]
pid = str(p["PacienteID"])

# ---------------- header ----------------
colA, colB = st.columns([1,3])
with colA:
    foto = str(p.get("FotoURL","") or "").strip()
    if foto:
        st.image(foto, width=220, caption=nome_sel)
    else:
        st.image("https://res.cloudinary.com/demo/image/upload/w_400,h_400,c_thumb,g_face,r_max/placeholder.png",
                 width=180, caption=nome_sel)

with colB:
    st.markdown(f"### {p.get('Nome','')}")
    chips = []
    status_norm = str(p.get("Status","")).strip().lower()
    prio_norm   = str(p.get("Prioridade","")).strip().lower()
    chips.append(f"<span class='badge {'chip-status-ativo' if status_norm=='ativo' else 'chip-status-inativo'}'>Status: {p.get('Status','-')}</span>")
    if prio_norm in ("alta","média","media","baixa"):
        cls = {"alta":"chip-prio-alta","média":"chip-prio-media","media":"chip-prio-media","baixa":"chip-prio-baixa"}[prio_norm]
        chips.append(f"<span class='badge {cls}'>Prioridade: {p.get('Prioridade','-')}</span>")
    st.markdown(" ".join(chips), unsafe_allow_html=True)
    st.write(f"**Responsável:** {p.get('Responsavel','-')}  |  **Telefone:** {p.get('Telefone','-')}")
    st.write(f"**Diagnóstico:** {p.get('Diagnostico','-')}")
    st.write(f"**Convênio:** {p.get('Convenio','-')}  |  **Email:** {p.get('Email','-')}")
    st.caption(p.get("Observacoes",""))

# KPIs rápidos
c1, c2, c3, c4 = st.columns(4)
ses_cli = df_ses[df_ses["PacienteID"].astype(str) == pid].copy()
pag_cli = df_pag[df_pag["PacienteID"].astype(str) == pid].copy()
rel_cli = df_rel[df_rel["PacienteID"].astype(str) == pid].copy()
ult_sess = ses_cli["Data"].dropna().astype(str).tolist()
ult_sess_dt = max((to_date(d) for d in ult_sess if to_date(d)), default=None)
c1.markdown(f"<div class='kpi'><h3>{len(ses_cli)}</h3><div class='lbl'>Sessões</div></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='kpi'><h3>{brl(pag_cli.get('Liquido',0).apply(to_float).sum())}</h3><div class='lbl'>Recebido (líquido)</div></div>", unsafe_allow_html=True)
c3.markdown(f"<div class='kpi'><h3>{len(rel_cli)}</h3><div class='lbl'>Relatórios</div></div>", unsafe_allow_html=True)
c4.markdown(f"<div class='kpi'><h3>{ult_sess_dt.strftime('%d/%m/%Y') if ult_sess_dt else '-'}</h3><div class='lbl'>Última sessão</div></div>", unsafe_allow_html=True)

st.divider()

# ---------------- abas ----------------
tab_over, tab_rel, tab_ses, tab_fin, tab_docs = st.tabs(["📌 Visão geral","🧾 Relatórios","🗓️ Sessões","💳 Financeiro","📎 Documentos"])

# ====== VISÃO GERAL ======
with tab_over:
    st.subheader("Linha do tempo")
    eventos = []

    # Relatórios
    for _, r in rel_cli.iterrows():
        d = to_date(r.get("Data"))
        if d:
            eventos.append({
                "dt": d,
                "tipo": f"Relatório · {r.get('Tipo','')}",
                "titulo": r.get("Titulo",""),
                "det": (str(r.get("Texto",""))[:160] + "…") if len(str(r.get("Texto",""))) > 160 else str(r.get("Texto",""))
            })

    # Sessões
    for _, r in ses_cli.iterrows():
        d = to_date(r.get("Data"))
        if d:
            eventos.append({
                "dt": d,
                "tipo": f"Sessão · {r.get('Status','')}",
                "titulo": r.get("Tipo","Terapia"),
                "det": f"{r.get('HoraInicio','')}–{r.get('HoraFim','')} • {r.get('Profissional','')}"
            })

    eventos = sorted(eventos, key=lambda x: x["dt"], reverse=True)
    if not eventos:
        st.info("Sem eventos ainda.")
    else:
        for ev in eventos[:40]:
            st.markdown(
                f"<div class='timeline-item'>"
                f"<div class='date'>{ev['dt'].strftime('%d/%m/%Y')} · {ev['tipo']}</div>"
                f"<div class='title'>{ev['titulo'] or '-'}</div>"
                f"<div class='small'>{ev['det'] or ''}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown("—")
    with st.expander("Editar observações e foto do paciente"):
        obs_n = st.text_area("Observações", value=str(p.get("Observacoes","")), height=120)
        foto_n = st.text_input("FotoURL", value=str(p.get("FotoURL","")))
        if st.button("Salvar alterações no cadastro"):
            # localizar linha na planilha e atualizar células
            idx_ws = df_pac.index[df_pac["PacienteID"].astype(str) == pid]
            if len(idx_ws) > 0:
                row = int(idx_ws[0]) + 2  # +2 por causa do header
                ws_pac.update_cell(row, PAC_COLS.index("Observacoes")+1, obs_n)
                ws_pac.update_cell(row, PAC_COLS.index("FotoURL")+1, foto_n)
                st.success("Cadastro atualizado.")
                st.cache_data.clear()
                st.rerun()

# ====== RELATÓRIOS ======
with tab_rel:
    st.subheader("Relatórios clínicos")
    colf1, colf2, colf3 = st.columns([1,1,2])
    with colf1:
        tipo_f = st.multiselect("Tipo", ["Anamnese","Plano","Evolução","Alta","Outro"], default=["Anamnese","Evolução","Plano","Alta","Outro"])
    with colf2:
        dt_ini = st.date_input("De", value=date.today() - timedelta(days=90))
        dt_fim = st.date_input("Até", value=date.today())
    with colf3:
        busca = st.text_input("Busca (título/trecho)", "")

    lst = rel_cli.copy()
    lst["__dt"] = lst["Data"].apply(to_date)
    if tipo_f: lst = lst[lst.get("Tipo","").isin(tipo_f)]
    lst = lst[(lst["__dt"]>=dt_ini) & (lst["__dt"]<=dt_fim)]
    if busca.strip():
        m = lst["Titulo"].astype(str).str.contains(busca, case=False, na=False) | \
            lst["Texto"].astype(str).str.contains(busca, case=False, na=False)
        lst = lst[m]
    lst = lst.sort_values("__dt", ascending=False)

    # seleção para export
    ids_sel = st.multiselect(
        "Selecionar relatórios para exportar",
        options=lst["RelatorioID"].astype(str).tolist(),
        format_func=lambda rid: f"{rid} · {lst.loc[lst['RelatorioID']==rid, 'Titulo'].values[0] if (lst['RelatorioID']==rid).any() else rid}"
    )

    # listar
    if lst.empty:
        st.info("Sem relatórios no filtro atual.")
    else:
        for _, r in lst.iterrows():
            rid = str(r.get("RelatorioID"))
            with st.expander(f"🧾 {r.get('Data','--')} — {r.get('Tipo','-')} · {r.get('Titulo','(sem título)')}", expanded=False):
                st.markdown(f"**Autor:** {r.get('Autor','-')}  ·  **Privado:** {r.get('Privado','Não')}")
                st.write(r.get("Texto",""))
                anex = str(r.get("AnexosURL","") or "").strip()
                if anex:
                    st.markdown(f"🔗 **Anexos:** {anex}")
                # excluir com confirmação local
                cc1, cc2 = st.columns([1,3])
                with cc1:
                    conf = st.checkbox(f"Confirmar exclusão ({rid})", key=f"conf_{rid}")
                with cc2:
                    if st.button("🗑️ Excluir relatório", key=f"del_{rid}") and conf:
                        # localizar linha e deletar
                        try:
                            idx = df_rel.index[df_rel["RelatorioID"].astype(str)==rid]
                            if len(idx)>0:
                                row = int(idx[0]) + 2
                                ws_rel.delete_rows(row)
                                st.success(f"Relatório {rid} excluído.")
                                st.cache_data.clear()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

    # exportar markdown
    if st.button("⬇️ Exportar selecionados (MD)") and ids_sel:
        md = [f"# Relatórios — {nome_sel}", ""]
        for rid in ids_sel:
            r = rel_cli[rel_cli["RelatorioID"].astype(str)==rid]
            if r.empty: continue
            rr = r.iloc[0]
            md += [
                f"## {rr.get('Data','--')} — {rr.get('Tipo','-')} · {rr.get('Titulo','(sem título)')}",
                f"**Autor:** {rr.get('Autor','-')}  ·  **Privado:** {rr.get('Privado','Não')}",
                "",
                str(rr.get("Texto","")),
                ""
            ]
        b = "\n".join(md).encode("utf-8")
        st.download_button("Baixar .md", data=b, file_name=f"relatorios_{pid}.md", mime="text/markdown")

    st.markdown("---")
    st.subheader("Novo relatório")
    with st.form("novo_rel"):
        colr1, colr2, colr3 = st.columns([1,1,1])
        with colr1:
            data_r = st.date_input("Data", value=date.today())
        with colr2:
            tipo_r = st.selectbox("Tipo", ["Anamnese","Evolução","Plano","Alta","Outro"], index=1)
        with colr3:
            priv = st.selectbox("Privado?", ["Não","Sim"], index=0)
        titulo_r = st.text_input("Título", "")
        texto_r  = st.text_area("Texto/Conteúdo", height=180)
        autor_r  = st.text_input("Autor", "Terapeuta")
        anexos_r = st.text_input("AnexosURL (opcional)", "")
        ok_r = st.form_submit_button("Salvar relatório")
        if ok_r:
            if not titulo_r.strip() and not texto_r.strip():
                st.error("Preencha ao menos Título ou Texto.")
                st.stop()
            rid = new_id("R")
            append_rows(ws_rel, [{
                "RelatorioID": rid,
                "PacienteID": pid,
                "Data": data_r.strftime("%d/%m/%Y"),
                "Tipo": tipo_r,
                "Titulo": titulo_r.strip(),
                "Texto": texto_r.strip(),
                "Autor": autor_r.strip(),
                "AnexosURL": anexos_r.strip(),
                "Privado": priv
            }], default_headers=REL_COLS)
            st.success(f"Relatório salvo ({rid}).")
            st.cache_data.clear()
            st.rerun()

# ====== SESSÕES ======
with tab_ses:
    st.subheader("Sessões do paciente")
    if ses_cli.empty:
        st.info("Sem sessões registradas.")
    else:
        ses_cli["__dt"] = ses_cli["Data"].apply(to_date)
        prox = ses_cli[ses_cli["__dt"] >= date.today()].sort_values("__dt")
        passadas = ses_cli[ses_cli["__dt"] < date.today()].sort_values("__dt", ascending=False)

        st.markdown("**Próximas**")
        if prox.empty: st.caption("—")
        else:
            st.dataframe(prox[["Data","HoraInicio","HoraFim","Profissional","Status","Tipo","Observacoes"]],
                        use_container_width=True, hide_index=True)
        st.markdown("**Histórico**")
        st.dataframe(passadas[["Data","HoraInicio","HoraFim","Profissional","Status","Tipo","ObjetivosTrabalhados","Observacoes"]],
                    use_container_width=True, hide_index=True)

# ====== FINANCEIRO ======
with tab_fin:
    st.subheader("Pagamentos")
    if pag_cli.empty:
        st.info("Sem pagamentos.")
    else:
        pag_cli["__dt"] = pag_cli["Data"].apply(to_date)
        pag_cli["__liq"] = pag_cli["Liquido"].apply(to_float)
        total = pag_cli["__liq"].sum()
        st.metric("Total recebido (líquido)", brl(total))
        st.dataframe(pag_cli[["Data","Forma","Bruto","Liquido","TaxaValor","Referencia","Obs"]],
                     use_container_width=True, hide_index=True)
        serie = (pag_cli.groupby("__dt")["__liq"].sum()
                 .reindex(sorted(pag_cli["__dt"].dropna().unique()), fill_value=0.0))
        if not serie.empty:
            st.line_chart(serie, use_container_width=True)

# ====== DOCUMENTOS ======
with tab_docs:
    st.subheader("Links anexados (relatórios)")
    anex_all = rel_cli["AnexosURL"].astype(str).tolist()
    anex_all = [a for a in anex_all if a and a.strip() and a.strip() != "-"]
    if not anex_all:
        st.info("Sem anexos.")
    else:
        for i, a in enumerate(anex_all, start=1):
            st.markdown(f"{i}. {a}")
