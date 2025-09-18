# pages/05_Fotos.py
# 🖼️ Upload de Fotos (Cloudinary) — Casulo

import unicodedata
import re
import streamlit as st
import cloudinary
import cloudinary.uploader
import cloudinary.api
from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Fotos (Cloudinary)", page_icon="🖼️", layout="wide")
st.title("🖼️ Upload de Fotos (Cloudinary)")

# ---------------- utils ----------------
def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "sem_nome"

# ---------------- Cloudinary config ----------------
cld = st.secrets.get("cloudinary") or st.secrets.get("CLOUDINARY")
if not cld:
    st.error("Config Cloudinary ausente. Adicione em st.secrets a seção [cloudinary] ou [CLOUDINARY] com cloud_name, api_key, api_secret.")
    st.stop()

cloudinary.config(
    cloud_name=cld.get("cloud_name"),
    api_key=cld.get("api_key"),
    api_secret=cld.get("api_secret"),
    secure=True,
)

FOLDER = "casulo/pacientes"

# ---------------- Sheets ----------------
ss = connect()

PAC_COLS = [
    "PacienteID","Nome","DataNascimento","Responsavel","Telefone","Email",
    "Diagnostico","Convenio","Status","Prioridade","FotoURL","CloudinaryID","Observacoes"
]
df_pac, ws_pac = read_ws(ss, "Pacientes", PAC_COLS)

if df_pac.empty:
    st.info("Nenhum paciente cadastrado ainda.")
    st.stop()

nomes = [""] + sorted(df_pac["Nome"].astype(str).str.strip().unique().tolist())
nome_sel = st.selectbox("Paciente", nomes, index=0, placeholder="Digite para buscar...")

if not nome_sel:
    st.stop()

# pega registro do paciente (primeiro matching pelo nome)
row = df_pac[df_pac["Nome"].astype(str).str.strip() == nome_sel].head(1)
if row.empty:
    st.error("Paciente não encontrado.")
    st.stop()

r = row.iloc[0]
pid = str(r["PacienteID"])
slug = _slugify(str(r["Nome"]))
public_id = f"{FOLDER}/{pid}_{slug}"

foto_atual = str(r.get("FotoURL", "") or "").strip()
cloudinary_id = str(r.get("CloudinaryID", "") or "").strip()

# tenta validar se o recurso existe no Cloudinary (se tivermos o ID)
resource_exists = False
if cloudinary_id:
    try:
        _ = cloudinary.api.resource(cloudinary_id)
        resource_exists = True
    except Exception:
        resource_exists = False

colA, colB = st.columns([1,2])
with colA:
    st.markdown("#### Foto atual")
    if foto_atual:
        st.image(foto_atual, width=220, caption=nome_sel)
    elif resource_exists:
        # monta URL a partir do public_id (entrega versão atual do Cloudinary)
        url_guess = cloudinary.CloudinaryImage(cloudinary_id).build_url()
        st.image(url_guess, width=220, caption=nome_sel)
    else:
        st.info("Sem foto cadastrada.")

with colB:
    st.markdown("#### Enviar nova foto")
    file = st.file_uploader("Imagem (JPG/PNG/WEBP)", type=["jpg", "jpeg", "png", "webp"])
    overwrite = st.checkbox("Sobrescrever se já existir", value=True)

    if file and st.button("📤 Enviar imagem", use_container_width=True):
        try:
            # Faz upload com public_id fixo
            up = cloudinary.uploader.upload(
                file,
                public_id=public_id,
                overwrite=overwrite,
                resource_type="image",
                unique_filename=False,
                use_filename=False,
                folder=None,   # public_id já inclui a pasta
            )
            url = up.get("secure_url", "")
            cid = up.get("public_id", public_id)

            # Atualiza planilha (mesma linha do paciente)
            idx = int(row.index[0])
            rownum = idx + 2  # +2 por causa do header 1-based
            col_foto = df_pac.columns.get_loc("FotoURL") + 1
            col_cid  = df_pac.columns.get_loc("CloudinaryID") + 1

            ws_pac.update_cell(rownum, col_foto, url)
            ws_pac.update_cell(rownum, col_cid,  cid)

            st.success("✅ Imagem enviada e planilha atualizada!")
            st.image(url, width=260)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro no upload: {e}")

st.markdown("---")
colC, colD = st.columns(2)
with colC:
    st.markdown("#### Apagar foto do paciente")
    if st.button("🗑️ Deletar do Cloudinary", use_container_width=True, disabled=not (cloudinary_id or public_id)):
        try:
            # tenta pelo CloudinaryID salvo; senão tenta pelo public_id padrão
            target_id = cloudinary_id or public_id
            cloudinary.uploader.destroy(target_id, resource_type="image")
            # limpa na planilha
            idx = int(row.index[0])
            rownum = idx + 2
            col_foto = df_pac.columns.get_loc("FotoURL") + 1
            col_cid  = df_pac.columns.get_loc("CloudinaryID") + 1
            ws_pac.update_cell(rownum, col_foto, "")
            ws_pac.update_cell(rownum, col_cid, "")
            st.success("Imagem deletada e planilha atualizada.")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao deletar: {e}")

with colD:
    st.markdown("#### Dica")
    st.caption("Padrão de ID: `casulo/pacientes/<PacienteID>_<slug-do-nome>`.\n"
               "Guardamos também o `CloudinaryID` na planilha para facilitar exclusões futuras.")

st.markdown("---")
st.subheader("🖼️ Galeria (miniaturas)")
thumb_cols = st.columns(6)
shown = 0
for _, pr in df_pac.iterrows():
    url = str(pr.get("FotoURL","") or "").strip()
    nome = str(pr.get("Nome","") or "").strip()
    if not url:
        continue
    with thumb_cols[shown % 6]:
        st.image(url, width=120, caption=nome)
    shown += 1
if shown == 0:
    st.info("Ainda não há imagens salvas.")
