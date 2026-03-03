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
# Dynamischer User-Agent gegen API-Sperren
geolocator = Nominatim(user_agent=f"integral_pro_v5_{random.randint(100,999)}", timeout=10)

# --- 2. LOGIK FÜR FEHLERTOLERANZ & VERIFIKATION ---
def check_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_verified_suggestions(query):
    """Sucht im Internet und gibt nur existierende Straßen zurück."""
    try:
        results = geolocator.geocode(f"{query}, Marburg-Biedenkopf", exactly_one=False, limit=3, addressdetails=True)
        if results:
            # Extrahiere nur den reinen Straßennamen aus der Antwort
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

# --- 4. UI: INPUT MIT VERIFIKATIONS-FILTER ---
st.title("🚀 INTEGRAL PRO — Verified Cache")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    
    with col_in:
        st.subheader("📥 Verifizierte Eingabe")
        m_s = st.text_input("Straßenname (wird geprüft)", key="m_s")
        m_h = st.text_input("Hnr", key="m_h")
        
        if m_s:
            suggestions = get_verified_suggestions(m_s)
            
            if suggestions:
                best_match = suggestions[0]
                score = check_similarity(m_s, best_match)
                
                # FALL A: Exakter Treffer oder sehr hohe Sicherheit (80%+)
                if score >= 0.8:
                    st.success(f"✅ Korrektur erkannt: **{best_match}**")
                    if st.button(f"'{best_match}' verifiziert speichern"):
                        full = f"{best_match} | {m_h}".strip(" |")
                        if full not in st.session_state.saved_manual_streets:
                            st.session_state.saved_manual_streets.append(full)
                            with open(STREETS_FILE, "w", encoding="utf-8") as f: 
                                f.write("\n".join(st.session_state.saved_manual_streets))
                            st.rerun()
                
                # FALL B: Mehrere Möglichkeiten (unter 80%)
                else:
                    st.warning("⚠️ Nicht eindeutig. Bitte wählen Sie den richtigen Namen:")
                    for s in suggestions:
                        if st.button(f"Speichere verifiziert: {s}", key=s):
                            full = f"{s} | {m_h}".strip(" |")
                            if full not in st.session_state.saved_manual_streets:
                                st.session_state.saved_manual_streets.append(full)
                                with open(STREETS_FILE, "w", encoding="utf-8") as f: 
                                    f.write("\n".join(st.session_state.saved_manual_streets))
                                st.rerun()
            else:
                st.error("❌ Straße im Internet unbekannt. Speichern blockiert.")

    with col_list:
        st.subheader("📝 Verifizierter Cache")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        st.data_editor(df, use_container_width=True, height=200, key="editor")
        
        if st.button("🗑️ Cache leeren", type="secondary"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 5. ANALYSE & KARTE ---
# (Wie gehabt: Greift nur auf die nun saubere 'saved_manual_streets' Liste zu)
