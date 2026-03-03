import streamlit as st
import pandas as pd
import os
import time

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-080" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL {SERIAL_NUMBER}", layout="wide")

START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 2. LOGIK ---
def get_clean_list(raw_input):
    if isinstance(raw_input, str):
        lines = raw_input.splitlines()
    else:
        lines = raw_input
    return sorted(list(set([l.strip() for l in lines if l.strip()])))

def save_to_disk(data_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(data_list))

if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = get_clean_list(f.read())
    else:
        st.session_state.main_list = []

# --- 3. UI ---
st.title(f"📍 Integral Dashboard {SERIAL_NUMBER}")

col_input, col_table = st.columns([1, 1])

with col_input:
    st.subheader("📥 Rohdaten-Editor")
    up = st.file_uploader("TXT Datei laden", type=["txt"])
    current_text = "\n".join(st.session_state.main_list)
    raw_text = st.text_area("Inhalt (Zeile für Zeile):", value=current_text, height=250)
    
    if up:
        new_content = up.getvalue().decode("utf-8")
        st.session_state.main_list = get_clean_list(current_text + "\n" + new_content)
        save_to_disk(st.session_state.main_list)
        st.rerun()

    if st.button("💾 SPEICHERN & SORTIEREN"):
        st.session_state.main_list = get_clean_list(raw_text)
        save_to_disk(st.session_state.main_list)
        st.rerun()

with col_table:
    st.subheader("🛠️ Korrektur-Tabelle")
    st.write(f"Anzahl: {len(st.session_state.main_list)} Adressen")
    df = pd.DataFrame(st.session_state.main_list, columns=["Adresse"])
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="ed_v80")
    
    if not edited_df.equals(df):
        st.session_state.main_list = get_clean_list(edited_df["Adresse"].tolist())
        save_to_disk(st.session_state.main_list)
        st.rerun()

# --- 4. FORTSCHRITTSANZEIGE & ANALYSE ---
st.markdown("---")
if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
    if not st.session_state.main_list:
        st.warning("Die Liste ist leer!")
    else:
        total = len(st.session_state.main_list)
        # Fortschrittsbalken initialisieren
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, adresse in enumerate(st.session_state.main_list):
            # Fortschritt berechnen (0.0 bis 1.0)
            percent = (i + 1) / total
            progress_bar.progress(percent)
            status_text.text(f"Verarbeite {i+1} von {total}: {adresse}")
            
            # Simulation der Rechenzeit (hier kommt später die echte OSM-Abfrage hin)
            time.sleep(0.1) 
            
        status_text.success(f"✅ Fertig! {total} Adressen erfolgreich verarbeitet.")
        st.balloons() # Kleiner visueller Effekt bei Abschluss

# Reset Button ganz unten
if st.button("🚨 ALLES LÖSCHEN"):
    if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
    st.session_state.main_list = []
    st.rerun()
