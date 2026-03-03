import streamlit as st
import pandas as pd
import os
import time

# --- 0. GOLDSTANDARD SETUP ---
SERIAL_NUMBER = "SN-083" 
st.set_page_config(page_title=f"INTEGRAL GOLD3000 {SERIAL_NUMBER}", layout="wide")

START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 1. LOGIK ---
def clean_and_sort(input_data):
    if isinstance(input_data, str):
        lines = input_data.splitlines()
    else:
        lines = input_data
    return sorted(list(set([l.strip() for l in lines if l.strip()])))

def save_data(data_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(data_list))

if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = clean_and_sort(f.read())
    else:
        st.session_state.main_list = []

# --- 2. FARB-LOGIK (Die "Markierung") ---
def color_rows(val):
    """
    Beispiel für farbige Markierung: 
    Einträge mit Hausnummer (Zahl am Ende) werden grün markiert,
    reine Straßennamen bleiben neutral.
    """
    import re
    if re.search(r'\d+', str(val)):
        return 'background-color: #d4edda; color: #155724' # Sanftes Grün
    return ''

# --- 3. UI ---
st.title(f"🚀 INTEGRAL GOLD3000 {SERIAL_NUMBER}")
st.caption(f"📍 Fokus: Farbige Straßenmarkierung & Stabilität")

col_editor, col_table = st.columns([1, 1])

with col_editor:
    st.subheader("📥 Rohdaten-Eingabe")
    up = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
    current_text = "\n".join(st.session_state.main_list)
    raw_input = st.text_area("Rohliste:", value=current_text, height=350)
    
    if up:
        imported_text = ""
        for f in up:
            imported_text += f.getvalue().decode("utf-8") + "\n"
        st.session_state.main_list = clean_and_sort(current_text + "\n" + imported_text)
        save_data(st.session_state.main_list)
        st.rerun()

with col_table:
    st.subheader("🛠️ Markierte Korrektur-Tabelle")
    st.write(f"Einträge: {len(st.session_state.main_list)}")
    
    df = pd.DataFrame(st.session_state.main_list, columns=["Zieladresse"])
    
    # Hier wenden wir die farbige Markierung an
    styled_df = df.style.map(color_rows, subset=['Zieladresse'])
    
    edited_df = st.data_editor(
        styled_df, # Wir geben das gestylte DF rein
        num_rows="dynamic", 
        use_container_width=True, 
        key=f"editor_v{len(st.session_state.main_list)}"
    )
    
    if not edited_df.equals(df):
        st.session_state.main_list = clean_and_sort(edited_df["Zieladresse"].tolist())
        save_data(st.session_state.main_list)
        st.rerun()

# --- 4. AKTIONEN ---
st.markdown("---")
if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    bar = st.progress(0)
    for i, addr in enumerate(st.session_state.main_list):
        bar.progress((i + 1) / len(st.session_state.main_list))
        time.sleep(0.01)
    st.success("Analyse abgeschlossen.")

if st.button("🚨 LISTE LEEREN"):
    if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
    st.session_state.main_list = []
    st.rerun()
