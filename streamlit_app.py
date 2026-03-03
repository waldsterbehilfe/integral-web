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
SERIAL_NUMBER = "SN-059" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Fixes Dunkel Design
bg_color, text_color, box_bg, border_color, accent_color = "#0E1117", "#FAFAFA", "#1E232B", "#31333F", "#1E88E5"

st.markdown(f"""
<style>
    .stApp {{background-color: {bg_color}; color: {text_color};}}
    .block-container {{padding-top: 1rem;}}
    h1, h2, h3 {{color: {accent_color} !important;}}
    .step-box {{background-color: {box_bg}; padding: 15px; border-radius: 5px; border: 1px solid {border_color}; margin-bottom: 15px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px; width: 100%;}}
    .metric-box {{background-color: {box_bg}; padding: 10px; border-radius: 5px; border-left: 5px solid {accent_color};}}
</style>
""", unsafe_allow_html=True)

# Verzeichnisse & Cache
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- LOGIK ---
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

def sync_editor():
    if "streets_editor" in st.session_state:
        df_current = st.session_state["streets_editor"]["data"]
        save_streets(df_current["Adresse (Strasse | Nr)"].tolist())

# Init Session State
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None

# --- UI HEADER ---
col_logo, col_title = st.columns([1, 8])
with col_logo: st.image(LOGO_URL, width=100)
with col_title: st.title(f"Integral Dashboard {SERIAL_NUMBER}")

# --- NEU: ZENTRALER IMPORT BEREICH ---
with st.expander("📥 Daten-Import & Verwaltung", expanded=not st.session_state.saved_manual_streets):
    col_in1, col_in2 = st.columns([2, 1])
    with col_in1:
        uploaded_file = st.file_uploader("*.txt Datei hochladen (eine Adresse pro Zeile)", type=["txt"])
        if uploaded_file:
            file_streets = [s.strip() for s in uploaded_file.getvalue().decode("utf-8").splitlines() if s.strip()]
            save_streets(st.session_state.saved_manual_streets + file_streets)
            st.success(f"{len(file_streets)} Adressen importiert!")
            time.sleep(1)
            st.rerun()
    with col_in2:
        st.write("Schnell-Aktionen")
        if st.button("🔄 Liste komplett leeren"):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.session_state.ort_sammlung = None
            st.rerun()
        if st.button("🗑️ Karten-Cache leeren"):
            if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR)
            st.rerun()

st.markdown("---")

# --- KONTROLL-LEISTE ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    search = st.text_input("📍 Einzelne Straße hinzufügen:", placeholder="z.B. Ringstraße 10")
    if search and st.button("➕ Hinzufügen"):
        save_streets(st.session_state.saved_manual_streets + [search])
        st.rerun()
with c2:
    st.write("") # Spacer
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()

# --- ANALYSE LOGIK (Kurzform für Übersicht) ---
# ... (Hier bleibt die verarbeite_strasse_erweitert Logik wie in SN-058) ...

# --- TABELLE ---
st.subheader(f"📝 Aktuelle Liste ({len(st.session_state.saved_manual_streets)} Einträge)")
df_display = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
st.data_editor(df_display, num_rows="dynamic", use_container_width=True, key="streets_editor", on_change=sync_editor)
