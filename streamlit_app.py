import streamlit as st
import pandas as pd
import os
import time

# --- 0. GOLDSTANDARD SETUP ---
SERIAL_NUMBER = "SN-082" 
# Modus: GOLD3000 (test 1 2 3)

st.set_page_config(page_title=f"INTEGRAL GOLD3000 {SERIAL_NUMBER}", layout="wide")

# Parameter
START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 1. LOGIK ---
def clean_and_sort(input_data):
    """Reinigt Rohdaten, entfernt Duplikate und sortiert A-Z"""
    if isinstance(input_data, str):
        lines = input_data.splitlines()
    else:
        lines = input_data
    return sorted(list(set([l.strip() for l in lines if l.strip()])))

def save_data(data_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(data_list))

# Initialisierung des Speichers
if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = clean_and_sort(f.read())
    else:
        st.session_state.main_list = []

# --- 2. UI HEADER ---
st.title(f"🚀 INTEGRAL GOLD3000 {SERIAL_NUMBER}")
st.caption(f"📍 Home-Base: {START_ADRESSE}")

# --- 3. DAS ARBEITSFELD ---
col_editor, col_table = st.columns([1, 1])

with col_editor:
    st.subheader("📥 Rohdaten / TXT-Import")
    up = st.file_uploader("Datei(en) hochladen", type=["txt"], accept_multiple_files=True)
    
    # Der bewährte Rohdaten-Editor
    current_text = "\n".join(st.session_state.main_list)
    raw_input = st.text_area("Vorschau & Direkteingabe:", value=current_text, height=350)
    
    if up:
        imported_text = ""
        for f in up:
            imported_text += f.getvalue().decode("utf-8") + "\n"
        st.session_state.main_list = clean_and_sort(current_text + "\n" + imported_text)
        save_data(st.session_state.main_list)
        st.rerun()

    if st.button("✅ DATEN ÜBERNEHMEN & SORTIEREN", use_container_width=True):
        st.session_state.main_list = clean_and_sort(raw_input)
        save_data(st.session_state.main_list)
        st.rerun()

with col_table:
    st.subheader("🛠️ Korrektur-Tabelle")
    st.write(f"Datensätze: {len(st.session_state.main_list)}")
    
    # Interaktive Tabelle für Hausnummern & Korrekturen
    df = pd.DataFrame(st.session_state.main_list, columns=["Zieladresse"])
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True, 
        key=f"editor_v{len(st.session_state.main_list)}" # Refresh bei Längenänderung
    )
    
    if not edited_df.equals(df):
        st.session_state.main_list = clean_and_sort(edited_df["Zieladresse"].tolist())
        save_data(st.session_state.main_list)
        st.rerun()

# --- 4. AKTIONEN & FORTSCHRITT ---
st.markdown("---")
b_col1, b_col2, b_col3 = st.columns([2, 1, 1])

with b_col1:
    if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
        if st.session_state.main_list:
            p_bar = st.progress(0)
            p_text = st.empty()
            for i, addr in enumerate(st.session_state.main_list):
                prog = (i + 1) / len(st.session_state.main_list)
                p_bar.progress(prog)
                p_text.text(f"Bearbeite {i+1}/{len(st.session_state.main_list)}: {addr}")
                time.sleep(0.02) # High-Speed Simulation
            p_text.success(f"✅ Analyse für {len(st.session_state.main_list)} Adressen abgeschlossen.")
        else:
            st.error("Keine Daten zum Analysieren gefunden!")

with b_col2:
    st.download_button("💾 EXPORT (*.txt)", data="\n".join(st.session_state.main_list), file_name="integral_liste.txt", use_container_width=True)

with b_col3:
    if st.button("🚨 LISTE LEEREN", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.main_list = []
        st.rerun()
