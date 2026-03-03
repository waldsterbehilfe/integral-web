import streamlit as st
import osmnx as ox
import folium
import re, os, random, time
import pandas as pd
from geopy.geocoders import Nominatim
from difflib import SequenceMatcher
import streamlit.components.v1 as components

# --- 1. SETUP ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_v5_{random.randint(100,999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def check_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_internet_verified(query):
    """Sucht online nach Validierung."""
    try:
        results = geolocator.geocode(f"{query}, Marburg-Biedenkopf", exactly_one=False, limit=3, addressdetails=True)
        if results:
            return [r.address.split(',')[0].strip() for r in results]
    except:
        pass
    return []

# --- 3. PERSISTENZ ---
if 'saved_manual_streets' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.saved_manual_streets = [l.strip() for l in f.readlines() if l.strip()]
    else:
        st.session_state.saved_manual_streets = []

# --- 4. UI: INPUT MIT HYBRID-LOGIK ---
st.title("🚀 INTEGRAL PRO — Hybrid Search")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    
    with col_in:
        st.subheader("📥 Eingabe & Validierung")
        m_s = st.text_input("Straßenname", key="m_s", placeholder="Eingabe prüfen...")
        m_h = st.text_input("Hnr", key="m_h", width=50)
        
        if m_s:
            full_raw = f"{m_s} | {m_h}".strip(" |")
            
            # STUFE 1: CACHE-CHECK (Exakt)
            if full_raw in st.session_state.saved_manual_streets:
                st.success("⚡ Sofort-Treffer im Cache (Kein Internet nötig).")
            else:
                # STUFE 2: INTERNET-CHECK (Validierung & Korrektur)
                suggestions = get_internet_verified(m_s)
                
                if suggestions:
                    best = suggestions[0]
                    score = check_similarity(m_s, best)
                    
                    if score >= 0.8:
                        st.info(f"💡 Vorschlag aus Internet: **{best}**")
                        if st.button(f"Verifiziert speichern: {best}"):
                            full_verified = f"{best} | {m_h}".strip(" |")
                            if full_verified not in st.session_state.saved_manual_streets:
                                st.session_state.saved_manual_streets.append(full_verified)
                                with open(STREETS_FILE, "w", encoding="utf-8") as f:
                                    f.write("\n".join(st.session_state.saved_manual_streets))
                                st.rerun()
                    else:
                        st.warning("Eingabe unsicher. Bitte einen Vorschlag wählen:")
                        for s in suggestions:
                            if st.button(f"Nutze: {s}", key=s):
                                # Speichern Logik
                                pass
                else:
                    st.error("❌ Unbekannt (Auch nicht im Internet gefunden).")

    with col_list:
        st.subheader("📝 Deine saubere Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Verifizierte Einträge"])
        st.data_editor(df, use_container_width=True, height=200)
        
        if st.button("🗑️ Cache löschen"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()
