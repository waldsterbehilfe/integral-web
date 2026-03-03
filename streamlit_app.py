import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
import networkx as nx
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-066" 

# --- 1. INITIALISIERUNG ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = []
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 2. SPEICHER-LOGIK (REPARIERT) ---
def save_streets(streets_list):
    # Filtern von leeren Einträgen und Duplikaten
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.saved_manual_streets = cleaned

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

# Einmaliges Laden beim Start
if not st.session_state.saved_manual_streets:
    st.session_state.saved_manual_streets = load_streets()

# --- 3. UI ---
st.title(f"Integral Dashboard {SERIAL_NUMBER}")

# Import & Reset
with st.expander("📂 Datei-Import & Reset"):
    up = st.file_uploader("*.txt hochladen", type=["txt"])
    if up:
        imported = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        new_list = st.session_state.saved_manual_streets + imported
        save_streets(new_list)
        st.rerun()
    
    if st.button("🚨 KOMPLETT-RESET"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.session_state.ort_sammlung = None
        st.rerun()

st.markdown("---")

# Editor Bereich (Der Fix)
if not st.session_state.ort_sammlung:
    st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)})")
    
    # Wir erstellen ein DataFrame für den Editor
    df_editor = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    
    # WICHTIG: Der Key 'streets_editor' sorgt dafür, dass Streamlit den State hält
    edited_df = st.data_editor(
        df_editor, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="streets_editor"
    )

    # Prüfen ob sich was geändert hat (Hinzugefügt, Gelöscht, Bearbeitet)
    if not edited_df.equals(df_editor):
        save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
        st.rerun()

    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()
