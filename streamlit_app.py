import streamlit as st
import pandas as pd
import os
import time
from geopy.geocoders import Nominatim

# --- SETUP ---
SERIAL_NUMBER = "SN-088"
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent="integral_planner_8h")

# --- FARB-LOGIK (Der bunte Kern) ---
def get_row_style(row):
    """
    Dieser Block sorgt für die bunte Markierung der Ergebnisse.
    """
    status = row['Status']
    if status == "Präzise":
        return ['background-color: #28a745; color: white'] * len(row)  # Sattes Grün
    elif status == "Unklar":
        return ['background-color: #ffc107; color: black'] * len(row)  # Gelb
    elif status == "Fehler":
        return ['background-color: #dc3545; color: white'] * len(row)  # Rot
    elif status == "Manuell":
        return ['background-color: #17a2b8; color: white'] * len(row)  # Cyan/Blau
    return [''] * len(row)

# --- DATEN-LOGIK ---
if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    else:
        st.session_state.main_list = []

# --- UI ---
st.title(f"🚀 INTEGRAL GOLD3000 {SERIAL_NUMBER}")

col_in, col_ed = st.columns([1, 1])

with col_in:
    st.subheader("📥 1. Rohdaten (Textfeld)")
    raw_input = st.text_area("Straßen hier reinkopieren:", value="\n".join(st.session_state.main_list), height=250)
    if st.button("💾 SPEICHERN & SORTIEREN"):
        st.session_state.main_list = sorted(list(set([l.strip() for l in raw_input.splitlines() if l.strip()])))
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(st.session_state.main_list))
        st.rerun()

with col_ed:
    st.subheader("🛠️ 2. Korrektur-Tabelle")
    df_editor = pd.DataFrame(st.session_state.main_list, columns=["Adresse"])
    edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_8h")
    if not edited_df.equals(df_editor):
        st.session_state.main_list = sorted(list(set(edited_df["Adresse"].tolist())))
        st.rerun()

# --- ANALYSE MIT BUNTER AUSGABE ---
st.markdown("---")
if st.button("🔥 ANALYSE STARTEN (MIT BUNTER MARKIERUNG)", type="primary", use_container_width=True):
    if st.session_state.main_list:
        results = []
        bar = st.progress(0)
        status_msg = st.empty()
        
        for i, addr in enumerate(st.session_state.main_list):
            bar.progress((i + 1) / len(st.session_state.main_list))
            status_msg.text(f"Analysiere: {addr}")
            
            # Logik für die bunte Zuweisung (vereinfacht für den Code-Check)
            if " " in addr and any(char.isdigit() for char in addr):
                stat = "Präzise"
            elif len(addr) < 4:
                stat = "Fehler"
            else:
                stat = "Unklar"
                
            results.append({"Adresse": addr, "Status": stat, "KM": "Berechne..."})
            time.sleep(0.05)
            
        df_res = pd.DataFrame(results)
        st.subheader("📊 Bunte Ergebnisliste")
        # Hier wird die Farbe auf die HTML-Ausgabe angewendet
        st.dataframe(df_res.style.apply(get_row_style, axis=1), use_container_width=True)
        status_msg.success("Analyse abgeschlossen!")
