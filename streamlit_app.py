import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-075" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

# Festgelegter Startpunkt (Goldstandard für die KM-Berechnung)
START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# Initialisierung
if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    else:
        st.session_state.main_list = []

if 'version_counter' not in st.session_state: st.session_state.version_counter = 0
if 'analysis_active' not in st.session_state: st.session_state.analysis_active = False

# --- 2. HILFSFUNKTIONEN ---
def sync_to_disk():
    st.session_state.main_list = sorted(list(set([str(s).strip() for s in st.session_state.main_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(st.session_state.main_list))

# --- 3. UI LAYOUT ---
st.title(f"🌐 Integral Dashboard {SERIAL_NUMBER}")
st.caption(f"📍 Festgelegter Startpunkt: {START_ADRESSE}")

# Kontroll-Zentrum
with st.container():
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        up = st.file_uploader("📂 Liste importieren (*.txt)", type=["txt"])
        if up:
            new_lines = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            st.session_state.main_list = list(set(st.session_state.main_list + new_lines))
            st.session_state.version_counter += 1
            sync_to_disk()
            st.rerun()

    with c2:
        st.write("##")
        if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
            st.session_state.analysis_active = True
        
        if st.button("🛑 STOPP", use_container_width=True):
            st.session_state.analysis_active = False
            st.rerun()

    with c3:
        st.write("##")
        if st.button("🚨 RESET", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.main_list = []
            st.session_state.version_counter += 1
            st.session_state.analysis_active = False
            st.rerun()

st.markdown("---")

# Tabelle
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.main_list)})")
df_display = pd.DataFrame(st.session_state.main_list, columns=["Adresse (Strasse | Nr)"])

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_v{st.session_state.version_counter}"
)

if not edited_df.equals(df_display):
    st.session_state.main_list = edited_df["Adresse (Strasse | Nr)"].tolist()
    sync_to_disk()

# --- 4. ANALYSE-ANZEIGE MIT KM-LOGIK ---
if st.session_state.analysis_active:
    st.markdown("---")
    st.subheader("📊 Routen-Analyse")
    
    if not st.session_state.main_list:
        st.warning("Bitte lade zuerst eine Straßenliste.")
    else:
        # Hier findet die Magie statt
        st.success(f"Berechne Route von: {START_ADRESSE}")
        
        # Statistiken (Platzhalter für die echten OSM-Werte)
        m1, m2, m3 = st.columns(3)
        m1.metric("Ziele", len(st.session_state.main_list))
        m2.metric("Gesamtstrecke", "Berechne...")
        m3.metric("Fahrtzeit (30km/h Ø)", "Berechne...")
        
        st.info("Soll ich die Karte mit der optimalen Route jetzt direkt einblenden?")
