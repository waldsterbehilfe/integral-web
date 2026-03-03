import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-062" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Integral Dark Design
bg_color, text_color, box_bg, border_color, accent_color = "#0E1117", "#FAFAFA", "#1E232B", "#31333F", "#1E88E5"

st.markdown(f"""
<style>
    .stApp {{background-color: {bg_color}; color: {text_color};}}
    .block-container {{padding-top: 1rem;}}
    h1, h2, h3 {{color: {accent_color} !important;}}
    .step-box {{background-color: {box_bg}; padding: 15px; border-radius: 5px; border: 1px solid {border_color}; margin-bottom: 15px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px; width: 100%;}}
    .metric-box {{background-color: {box_bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {accent_color}; margin-bottom: 10px;}}
</style>
""", unsafe_allow_html=True)

# Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- FUNKTIONEN ---
def save_streets(streets_list):
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.saved_manual_streets = cleaned

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

# Init Session State
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- UI HEADER ---
c_l, c_t = st.columns([1, 7])
with c_l: st.image(LOGO_URL, width=100)
with c_t: st.title(f"Integral Dashboard {SERIAL_NUMBER}")

# 1. Zeile: Import & Steuerung
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    up = st.file_uploader("📂 Liste importieren (*.txt)", type=["txt"])
    if up:
        imported = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        save_streets(st.session_state.saved_manual_streets + imported)
        st.rerun()
with col2:
    st.write("##")
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()
with col3:
    st.write("##")
    if st.button("🔄 KOMPLETT-RESET"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets, st.session_state.ort_sammlung = [], None
        st.rerun()

st.markdown("---")

# 2. Zeile: Suche & Tabelle
if not st.session_state.ort_sammlung:
    s_col1, s_col2 = st.columns([1, 2])
    with s_col1:
        st.subheader("📍 Einzelsuche")
        new_s = st.text_input("Straße & Nr:", placeholder="Hauptstr 1")
        if st.button("➕ Hinzufügen") and new_s:
            save_streets(st.session_state.saved_manual_streets + [new_s])
            st.rerun()
    with s_col2:
        st.subheader(f"📝 Liste ({len(st.session_state.saved_manual_streets)})")
        df_init = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
        
        # Der Editor aktualisiert direkt das File, wenn Änderungen vorgenommen werden
        edited_df = st.data_editor(df_init, num_rows="dynamic", use_container_width=True, key="streets_editor")
        
        # Falls sich die Daten im Vergleich zum State geändert haben -> Speichern
        if not edited_df.equals(df_init):
            save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
            st.rerun()

# --- ANALYSE BEREICH (wie SN-060) ---
if st.session_state.run_processing:
    # ... (Verarbeitungs-Logik von vorher hier einsetzen) ...
    st.write("Analyse läuft...") # Platzhalter für die Loop
    st.session_state.run_processing = False
