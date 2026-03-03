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
SERIAL_NUMBER = "SN-064" 

# --- 1. SETUP & INITIALISIERUNG ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

# WICHTIG: Alle States am Anfang definieren, damit Zeile 33 nicht mehr abstürzt
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = []
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'echte_km_daten' not in st.session_state: st.session_state.echte_km_daten = {}

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"
accent_color = "#1E88E5"

st.markdown(f"""
<style>
    .stApp {{background-color: #0E1117; color: #FAFAFA;}}
    .metric-box {{background-color: #1E232B; padding: 15px; border-radius: 10px; border-left: 5px solid {accent_color}; margin-bottom: 10px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px; width: 100%;}}
</style>
""", unsafe_allow_html=True)

# Pfade & Cache
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- FUNKTIONEN ---
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

# Initiales Laden der Datei
if not st.session_state.saved_manual_streets:
    st.session_state.saved_manual_streets = load_streets()

# --- ROUTEN BERECHNUNG ---
def berechne_echte_tour(ort, items):
    try:
        # Grobe Netz-Analyse
        G = ox.graph_from_address(f"{ort}, Marburg-Biedenkopf", network_type='drive', dist=2000)
        G = ox.project_graph(G, to_crs='EPSG:32632')
        points = [i["gdf"].to_crs(epsg=32632).geometry.unary_union.centroid for i in items]
        nodes = [ox.nearest_nodes(G, p.x, p.y) for p in points]
        
        dist_m = 0
        curr = nodes[0]
        nodes_to_visit = nodes[1:]
        while nodes_to_visit:
            nxt = min(nodes_to_visit, key=lambda n: nx.shortest_path_length(G, curr, n, weight='length'))
            dist_m += nx.shortest_path_length(G, curr, nxt, weight='length')
            curr = nxt
            nodes_to_visit.remove(nxt)
            
        own_m = sum(i["laenge"] for i in items)
        km_gesamt = (dist_m + own_m) / 1000
        zeit_h = km_gesamt / 30 # 30 km/h Schnitt
        return {"km": km_gesamt, "zeit": zeit_h}
    except:
        # Fallback bei Fehlern
        fallback_km = (sum(i["laenge"] for i in items) / 1000) * 1.4
        return {"km": fallback_km, "zeit": fallback_km / 30}

# --- UI ---
st.title(f"Integral Dashboard {SERIAL_NUMBER}")

# Import Bereich
with st.expander("📥 Datei-Import & Reset", expanded=False):
    up = st.file_uploader("*.txt Datei", type=["txt"])
    if up:
        imported = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        save_streets(st.session_state.saved_manual_streets + imported)
        st.rerun()
    if st.button("🗑️ ALLES LÖSCHEN"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.session_state.ort_sammlung = None
        st.session_state.echte_km_daten = {}
        st.rerun()

# Haupt-Buttons
c1, c2 = st.columns(2)
with c1:
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()
with c2:
    if st.session_state.ort_sammlung:
        if st.button("🛣️ ROUTE & ZEIT OPTIMIEREN"):
            with st.spinner("Berechne Fahrwege..."):
                for ort, items in st.session_state.ort_sammlung.items():
                    st.session_state.echte_km_daten[ort] = berechne_echte_tour(ort, items)
            st.success("Planung abgeschlossen!")

# Tabelle oder Ergebnisse
if not st.session_state.ort_sammlung:
    st.subheader("📝 Aktuelle Straßenliste")
    df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if not edited.equals(df):
        save_streets(edited["Adresse (Strasse | Nr)"].tolist())
        st.rerun()
else:
    # Ergebnis-Display
    total_km = sum(d["km"] for d in st.session_state.echte_km_daten.values()) if st.session_state.echte_km_daten else 0
    m1, m2 = st.columns(2)
    m1.markdown(f"<div class='metric-box'><b>Gesamtfahrstrecke (geplant):</b><br><h2>{total_km:.2f} km</h2></div>", unsafe_allow_html=True)
    m2.markdown(f"<div class='metric-box'><b>Geschätzte Dauer (30km/h):</b><br><h2>{total_km/30:.1f} Std.</h2></div>", unsafe_allow_html=True)
    
    # Hier folgt der Rest der Karten-Anzeige (wie SN-062)
