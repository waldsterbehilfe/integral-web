import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3001"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. CACHE-LOGIK ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
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
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None

# --- 4. IMPORT-TRIGGER (GANZ OBEN FÜR SOFORT-EFFEKT) ---
# Wir platzieren den Uploader hier, damit er vor der Anzeige der Liste verarbeitet wird
uploaded_files = st.file_uploader("*.txt Datei hier ablegen für Sofort-Import", type=["txt"], accept_multiple_files=True, key="main_uploader")

if uploaded_files:
    new_entries = []
    for f in uploaded_files:
        content = f.getvalue().decode("utf-8").splitlines()
        new_entries.extend([line.strip() for line in content if line.strip()])
    
    # Abgleich mit bestehenden Daten
    old_list = st.session_state.saved_manual_streets
    combined = sorted(list(set(old_list + new_entries)))
    
    if len(combined) > len(old_list):
        st.session_state.saved_manual_streets = combined
        save_streets(combined)
        st.rerun() # Zwingt Streamlit, die Liste sofort neu zu zeichnen

# --- 5. UI: HAUPTBEREICH ---
st.title("🚀 INTEGRAL PRO")
st.info(f"**Cache-Status:** {len(st.session_state.saved_manual_streets)} Straßen geladen.")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    
    with col_in:
        st.subheader("➕ Manueller Input")
        c1, c2 = st.columns([3, 1])
        m_str = c1.text_input("Straße", key="m_str_input")
        m_hnr = c2.text_input("Hnr", key="m_hnr_input")
        if st.button("Hinzufügen", use_container_width=True):
            if m_str:
                entry = f"{m_str} | {m_hnr}".strip(" |")
                if entry not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(entry)
                    save_streets(st.session_state.saved_manual_streets)
                    st.rerun()

    with col_list:
        st.subheader("📝 Liste & Korrektur")
        if st.session_state.saved_manual_streets:
            df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
            # Der Editor erlaubt direktes Löschen und Ändern
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", height=250)
            
            c_save, c_del = st.columns(2)
            if c_save.button("💾 Änderungen speichern", use_container_width=True):
                st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()
                
            if c_del.button("🗑️ Cache leeren", use_container_width=True):
                st.session_state.saved_manual_streets = []
                save_streets([])
                st.rerun()
        else:
            st.warning("Die Liste ist aktuell leer.")

# --- 6. STEUERUNG ---
st.divider()
c_run, c_stop = st.columns(2)

if c_run.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.rerun()

if c_stop.button("🛑 ABBRUCH", type="secondary", use_container_width=True):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False
    st.rerun()

# --- 7. ANALYSE-LOGIK ---
if st.session_state.run_processing:
    # ... (Analyse-Schleife wie zuvor mit Mouseover-Funktion)
    pass
