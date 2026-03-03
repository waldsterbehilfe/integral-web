import streamlit as st
import osmnx as ox
import folium
import io, re, os, random
import pandas as pd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. SETUP ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
# Eindeutiger User-Agent für stabile API-Abfragen
geolocator = Nominatim(user_agent=f"integral_pro_validator_{random.randint(1000,9999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

# --- 3. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False

# --- 4. UI: HEADER ---
st.title("🚀 INTEGRAL PRO — Intelligent Input")
st.info(f"**Gespeicherte Straßen:** {len(st.session_state.saved_manual_streets)}")

# --- 5. EINGABE MIT LIVE-ABGLEICH & ZIEL-ANZEIGE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    
    with col_in:
        st.subheader("📥 Neue Straße prüfen")
        c1, c2 = st.columns([3, 1])
        m_s = c1.text_input("Straßenname", key="m_s", placeholder="z.B. Universitätsstraße")
        m_h = c2.text_input("Hnr", key="m_h", placeholder="7")
        
        target_found = False
        if m_s:
            try:
                # Live-Abgleich mit dem Internet
                with st.spinner("Prüfe Zielort im Internet..."):
                    check_query = f"{m_s}, Marburg-Biedenkopf"
                    location = geolocator.geocode(check_query, addressdetails=True)
                    
                    if location:
                        addr = location.raw.get('address', {})
                        # Zielort extrahieren (Stadtteil oder Gemeinde)
                        ziel = addr.get('village') or addr.get('suburb') or addr.get('city') or addr.get('town')
                        st.success(f"✅ **Ziel erkannt:** {m_s} liegt in **{ziel}**")
                        target_found = True
                    else:
                        st.warning("⚠️ Straße nicht gefunden. Bitte Schreibweise prüfen (z.B. 'Str.' zu 'Straße').")
            except:
                st.error("Verbindung zum Geocoding-Dienst unterbrochen.")

        if st.button("➕ In Liste speichern", use_container_width=True, disabled=not m_s):
            full_entry = f"{m_s} | {m_h}".strip(" |")
            if full_entry not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(full_entry)
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()

    with col_list:
        st.subheader("📝 Aktueller Cache")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", height=200)
        
        c_sv, c_cl = st.columns(2)
        if c_sv.button("💾 Liste korrigieren", use_container_width=True):
            st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
            save_streets(st.session_state.saved_manual_streets)
            st.rerun()
        if c_cl.button("🗑️ Cache leeren", use_container_width=True):
            st.session_state.saved_manual_streets = []
            save_streets([])
            st.rerun()

# --- 6. STEUERUNG & ANALYSE (Punkte wie gehabt) ---
# [Hier folgt der Rest des GOLD3002 Codes für Analyse und Karte]
