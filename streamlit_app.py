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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ-FUNKTIONEN ---
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
st.title("🚀 INTEGRAL PRO")
st.info(f"**Cache:** {len(st.session_state.saved_manual_streets)} bekannte Einträge.")

# --- 5. INPUT MIT SPEED-LAYER LOGIK ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    
    with col_in:
        st.subheader("📥 Dateneingabe")
        c1, c2 = st.columns([3, 1])
        m_s = c1.text_input("Straße", key="m_s", placeholder="z.B. Frankfurter Str.")
        m_h = c2.text_input("Hnr", key="m_h", placeholder="1")
        
        if st.button("✅ Hinzufügen / Prüfen", use_container_width=True):
            if m_s:
                full_entry = f"{m_s} | {m_h}".strip(" |")
                
                # SPEED-LAYER: Ist es exakt so schon im Cache?
                if full_entry in st.session_state.saved_manual_streets:
                    st.success(f"'{full_entry}' wurde sofort aus dem Cache geladen.")
                else:
                    # PLAUSIBILITÄT: Nur wenn nicht im Cache, wird online geprüft
                    with st.spinner("Prüfe neue Straße..."):
                        test_loc = geolocator.geocode(f"{m_s}, Marburg-Biedenkopf")
                        if test_loc:
                            st.session_state.saved_manual_streets.append(full_entry)
                            save_streets(st.session_state.saved_manual_streets)
                            st.success(f"Neu erkannt und gespeichert: {full_entry}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Schreibfehler oder Straße in der Region unbekannt.")

    with col_list:
        st.subheader("📝 Lokaler Cache")
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

# --- 6. ANALYSE-LOGIK (Verkürzt für Übersicht) ---
st.divider()
if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    # [Rest der Analyse-Logik wie in GOLD3001/3002]
