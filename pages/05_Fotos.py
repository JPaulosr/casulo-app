# pages/05_Fotos.py
# 🖼️ Upload de Fotos (Cloudinary) — Casulo

import unicodedata, re
import streamlit as st
import cloudinary
import cloudinary.uploader
import cloudinary.api
from utils_casulo import connect, read_ws

st.set_page_config(page_title="Casulo — Fotos (Cloudinary)", page_icon="🖼️", layout="wide")
st.title("🖼️ Upload de Fotos (Cloudinary)")

# ---------- utils ----------
def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "sem_nome"

# ---------- Cloudinary ----------
cld = st.secrets.get("cloudinary") or st.secrets.get("CLOUDINARY")
if not cld:
    st.error("Faltam secrets do Cloudinary: [cloudinary] cloud_name/api_key/api_secret (e opcionalmente folder).")
    st.stop()

cloudinary.config(
    cloud_name=cld.get("cloud_name"),
    api_key=cld.get("api_key"),
    api_secret=cld.get("api_secret"),
    secure=True,
)

BASE_FOLDER = cld.get("folder") or "Clientes Casulo"   # padrão = sua pasta
SUB_OPTIONS = [BASE_FOLDER, f"{BASE_FOLDER}/Logo"]

st.caption(f"Pasta base padrão: **{BASE_FOLDER}**")
dest_folder = st.selectbox("📁 Pasta de destino no Cloudinary", SUB_OPTIONS, index=0)

# ---------- Sheets ----------
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

row = df_pac[df_pac["Nome"].astype(str).str.strip() == nome_sel].head(1)
if row.empty:
    st.error("Paciente não encontrado.")
    st.stop()

r = row.iloc[0]
pid = str(r["PacienteID"])
slug = _slugify(str(r["Nome"]))
public_id_base = f"{pid}_{slug}"  # o folder é escolhido separadamente
cloudinary_id = (r.get("CloudinaryID") or "").strip()
foto_atual = (r.get("FotoURL") or "").strip()

# Mostrar foto atual
st.markdown("#### Foto atual")
if foto_atual:
    st.image(foto_atual, width=220, caption=nome_sel)
elif cloudinary_id:
    try:
        _ = cloudinary.api.resource(cloudinary_id)
        url_guess = cloudinary.CloudinaryImage(cloudinary_id).build_url()
        st.image(url_guess, width=220, caption=nome_sel)
    except Exception:
        st.info("Sem foto cadastrada.")
else:
    st.info("Sem foto cadastrada.")

st.markdown("---")
st.markdown("#### Enviar nova foto")

file = st.file_uploader("Imagem (JPG/PNG/WEBP)", type=["jpg","jpeg","png","webp"])
overwrite = st.checkbox("Sobrescrever se já existir", value=True)

if file and st.button("📤 Enviar imagem", use_container_width=True):
    try:
        up = cloudinary.uploader.upload(
            file,
            folder=dest_folder,              # <<<<<<<<<< pasta de destino (ex.: "Clientes Casulo" ou ".../Logo")
            public_id=public_id_base,        # não inclua a pasta aqui
            overwrite=overwrite,
            resource_type="image",
            unique_filename=False,
            use_filename=False,
        )
        url = up.get("secure_url", "")
        cid = up.get("public_id", "")       # vem como "<folder>/<public_id>"

        # Atualiza planilha
        idx = int(row.index[0])
        rownum = idx + 2
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
st.markdown("#### Apagar foto do paciente")
if st.button("🗑️ Deletar do Cloudinary", use_container_width=True, disabled=not cloudinary_id):
    try:
        cloudinary.uploader.destroy(cloudinary_id, resource_type="image")
        idx = int(row.index[0]); rownum = idx + 2
        col_foto = df_pac.columns.get_loc("FotoURL") + 1
        col_cid  = df_pac.columns.get_loc("CloudinaryID") + 1
        ws_pac.update_cell(rownum, col_foto, "")
        ws_pac.update_cell(rownum, col_cid, "")
        st.success("Imagem deletada e planilha atualizada.")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")

st.markdown("---")
st.subheader("🖼️ Galeria (miniaturas)")
cols = st.columns(6)
shown = 0
for _, pr in df_pac.iterrows():
    url = (pr.get("FotoURL") or "").strip()
    nome = (pr.get("Nome") or "").strip()
    if not url:
        continue
    with cols[shown % 6]:
        st.image(url, width=120, caption=nome)
    shown += 1
if shown == 0:
    st.info("Ainda não há imagens salvas.")
