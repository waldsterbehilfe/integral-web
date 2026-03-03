import streamlit as st
import osmnx as ox
import folium
import io, re, os, time
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="INTEGRAL PRO GOLD", layout="wide", page_icon="📈")

# --- HILFSFUNKTIONEN ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            return sorted(list(set(lines)))
    return []

def save_streets(streets_list):
    cleaned = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    return cleaned

# Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None

# --- UI ---
st.title("🚀 INTEGRAL PRO — Goldstandard")

c1, c2 = st.columns([1, 1])

with c2:
    st.subheader("📝 Zentrale Eingabeliste")
    # Lösung Fehler 1: Wir nutzen einen Key für das Widget, um den State stabil zu halten
    input_text = st.text_area(
        "Straßen hier editieren:", 
        value="\n".join(st.session_state.saved_manual_streets), 
        height=350,
        key="street_input_field"
    )
    
    # Speichern Button für Stabilität (statt Live-Sync bei jedem Tastendruck)
    if st.button("💾 Liste speichern & sortieren"):
        current_list = [s.strip() for s in input_text.splitlines() if s.strip()]
        st.session_state.saved_manual_streets = save_streets(current_list)
        st.success("Gespeichert!")
        st.rerun()

with c1:
    st.subheader("🔍 Lokale Suche")
    search_q = st.text_input("In deiner Liste suchen:", placeholder="Tippe Straßennamen...")
    if search_q:
        results = [s for s in st.session_state.saved_manual_streets if search_q.lower() in s.lower()]
        for r in results[:5]: st.write(f"✅ {r}")

st.divider()

# --- VERARBEITUNG ---
geolocator = Nominatim(user_agent="integral_pro_v92")

def verarbeite_strasse_safe(strasse):
    # Lösung Fehler 3: Kurze Pause, um Nominatim Limits einzuhalten
    time.sleep(0.2) 
    # ... (Rest deiner verarbeite_strasse Logik bleibt gleich)
    # Hier der Vollständigkeit halber nur der Kern:
    try:
        # Dein Geocoding-Code...
        return {"success": True, "original": strasse, "ort": "Beispiel"} # Vereinfacht für das Beispiel
    except:
        return {"success": False, "original": strasse}

# DOWNLOAD SEKTION (Erweiterung)
if st.session_state.saved_manual_streets:
    st.download_button(
        "📥 Liste als TXT exportieren",
        "\n".join(st.session_state.saved_manual_streets),
        "gold_liste.txt"
    )
