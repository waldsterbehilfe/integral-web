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

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ-FUNKTIONEN ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        try:
            with open(STREETS_FILE, "r", encoding="utf-8") as f:
                return sorted(list(set(line.strip() for line in f if line.strip())))
        except: return []
    return []

def save_streets(streets_list):
    try:
        clean_list = sorted(list(set(s.strip() for s in streets_list if s.strip())))
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_list))
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")

# --- 3. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False

# --- 4. UI-KOMPONENTEN ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Version: {SERIAL_NUMBER} | Fokus: Marburg-Biedenkopf")

# Der Container für den sofortigen Daten-Import
with st.container(border=True):
    col_up, col_list = st.columns([1, 1])
    
    with col_up:
        st.subheader("📥 TXT-Upload")
        # Jede Änderung hier löst einen sofortigen Rerun aus
        uploaded_files = st.file_uploader(
            "Wähle *.txt Dateien aus", 
            type=["txt"], 
            accept_multiple_files=True,
            key="file_loader"
        )
        
        if uploaded_files:
            new_entries = []
            for f in uploaded_files:
                # Datei zeilenweise auslesen
                lines = f.getvalue().decode("utf-8").splitlines()
                new_entries.extend([l.strip() for l in lines if l.strip()])
            
            # Bestehende Liste nehmen, neue hinzufügen, Duplikate entfernen
            current_list = st.session_state.saved_manual_streets
            updated_list = sorted(list(set(current_list + new_entries)))
            
            # Nur speichern und neu laden, wenn sich wirklich etwas geändert hat
            if len(updated_list) > len(current_list):
                st.session_state.saved_manual_streets = updated_list
                save_streets(updated_list)
                st.success(f"Erfolg: {len(new_entries)} Einträge verarbeitet.")
                time.sleep(0.5)
                st.rerun()

    with col_list:
        st.subheader(f"📝 Aktuelle Liste ({len(st.session_state.saved_manual_streets)})")
        if st.session_state.saved_manual_streets:
            # Anzeige als DataFrame für bessere Übersicht
            st.dataframe(
                pd.DataFrame(st.session_state.saved_manual_streets, columns=["Straßenname"]), 
                use_container_width=True, 
                height=200
            )
            if st.button("🗑️ Liste komplett leeren"):
                st.session_state.saved_manual_streets = []
                save_streets([])
                st.rerun()
        else:
            st.info("Warten auf Daten-Upload...")

# --- 5. ANALYSE-LOGIK ---
st.divider()

if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    if not st.session_state.saved_manual_streets:
        st.warning("Bitte zuerst Straßen hochladen!")
    else:
        st.session_state.run_processing = True

if st.session_state.run_processing:
    # Hier folgt die bereits geprüfte Analyse-Logik (ox.features_from_address etc.)
    # Zur Übersichtlichkeit hier verkürzt - die Mechanik bleibt identisch zum Vorherigen
    st.info("Analyse läuft... (Hier wird die Karte generiert)")
    # [Rest der Analyse-Logik wie zuvor]
    st.session_state.run_processing = False
