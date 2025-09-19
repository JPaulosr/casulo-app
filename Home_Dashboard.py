# Home_Dashboard.py
# 🦋 Casulo | Dashboard

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, time
from utils_casulo import connect, read_ws  # ✅ mantenha só este import

st.set_page_config(page_title="Casulo — Dashboard", page_icon="🦋", layout="wide")

# --- HERO (logo + título + subtítulo) ---
LOGO_URL = "https://res.cloudinary.com/db8ipmete/image/upload/v1758238516/Captura_de_tela_2025-09-18_151051_cvqmh9.png"

st.markdown(f"""
<style>
/* container do hero */
.casulo-hero {{
  display: flex; align-items: center; gap: 18px;
  padding: 18px 22px; border-radius: 18px;
  background: linear-gradient(135deg, rgba(30,41,59,.55), rgba(2,6,23,.55));
  border: 1px solid rgba(148,163,184,.18);
  box-shadow: 0 10px 30px rgba(0,0,0,.25) inset, 0 6px 20px rgba(2,6,23,.25);
  margin-bottom: 12px;
}
.casulo-hero .logo {{
  width: 54px; height: 54px; border-radius: 12px;
  background: rgba(255,255,255,.06);
  padding: 6px; object-fit: contain;
  box-shadow: 0 2px 10px rgba(0,0,0,.25);
}}
.casulo-hero .title {{
  font-size: 28px; font-weight: 800; line-height: 1.2; margin: 0;
}}
.casulo-hero .subtitle {{
  margin-top: 2px; color: #94a3b8; font-size: 14px;
}}
/* reduzir respiro no topo do container */
.main .block-container {{ padding-top: 1rem; }}
/* chips/cards usados abaixo */
.badge {{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;}}
.st-status-agendada  {{background:rgba(148,163,184,.20); color:#e2e8f0;}}
.st-status-confirmada{{background:rgba(34,197,94,.18);  color:#86efac;}}
.st-status-realizada {{background:rgba(99,102,241,.18); color:#c7d2fe;}}
.st-status-falta     {{background:rgba(239,68,68,.18);  color:#fecaca;}}
.st-status-cancelada {{background:rgba(100,116,139,.18);color:#cbd5e1; text-decoration:line-through;}}
.small {{font-size:12px;color:#94a3b8}}
.item {{
  padding:10px 12px;
  border:1px solid rgba(148,163,184,.18);
  border-radius:12px;
  margin-bottom:8px;
  background:rgba(255,255,255,.03);
}}
.item:hover {{background:rgba(255,255,255,.05)}}
.hdim {{opacity:.85}}
</style>

<div class="casulo-hero">
  <img class="logo" src="{LOGO_URL}" alt="Casulo">
  <div>
    <h1 class="title">Casulo | Dashboard</h1>
    <div class="subtitle">Visão da semana • Agenda & Finanças da clínica</div>
  </div>
</div>
""", unsafe_allow_html=True)
