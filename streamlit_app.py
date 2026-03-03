import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from datetime import datetime
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. SETUP & KONFIGURATION ---
SERIAL_NUMBER = "SN-029-GOLD3001"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# OSMnx & Geocoder
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f.readlines() if l.strip()]
    return []

def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

# --- 3. SESSION STATE INITIALISIERUNG ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False

# --- 4. SOFORT-IMPORT LOGIK (TRIGGER) ---
# Dieser Block muss vor dem UI stehen, um den State sofort zu aktualisieren
uploaded_files = st.sidebar.file_uploader("Schnell-Import (TXT)", type=["txt"], accept_multiple_files=True, key="uploader_sidebar")
if uploaded_files:
    new_entries = []
    for f in uploaded_files:
        lines = f.getvalue().decode("utf-8").splitlines()
        new_entries.extend([l.strip() for l in lines if l.strip()])
    
    # Filtern auf echte Neuerungen
    current = st.session_state.saved_manual_streets
    fresh = [n for n in new_entries if n not in current]
    
    if fresh:
        st.session_state.saved_manual_streets.extend(fresh)
        save_streets(st.session_state.saved_manual_streets)
        st.rerun()

# --- 5. UI: HAUPTBEREICH ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Cache-Status: {len(st.session_state.saved_manual_streets)} Straßen geladen")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])

    with col_in:
        st.subheader("➕ Manueller Input")
        c1, c2 = st.columns([3, 1])
        new_s = c1.text_input("Straße", key="manual_s")
        new_h = c2.text_input("Hnr", key="manual_h")
        if st.button("Hinzufügen", use_container_width=True):
            if new_s:
                entry = f"{new_s} | {new_h}".strip(" |")
                if entry not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(entry)
                    save_streets(st.session_state.saved_manual_streets)
                    st.rerun()

    with col_list:
        st.subheader("📝 Liste & Korrektur")
        # Data Editor für Live-Korrekturen
        df_display = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df_display, use_container_width=True, num_rows="dynamic", height=200)
        
        col_edit1, col_edit2 = st.columns(2)
        if col_edit1.button("💾 Speichern", use_container_width=True):
            st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
            save_streets(st.session_state.saved_manual_streets)
            st.rerun()
            
        if col_edit2.button("🗑️ Leer", use_container_width=True):
            st.session_state.saved_manual_streets = []
            save_streets([])
            st.rerun()

# --- 6. STEUERUNG ---
st.divider()
c_go, c_halt = st.columns(2)
if c_go.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.rerun()

if c_halt.button("🛑 ABBRUCH", type="secondary", use_container_width=True):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False

# --- 7. VERARBEITUNG (VERKÜRZT) ---
if st.session_state.run_processing:
    with st.status("Suche Geometrien...", expanded=True) as status:
        # Hier läuft die ox-Logik (wie im vorherigen Turn)
        # Wenn stop_requested == True -> break
        pass
