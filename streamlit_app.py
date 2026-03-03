import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-077" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# Initialisierung der Zähler
if 'duplicate_count' not in st.session_state: st.session_state.duplicate_count = 0

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            # Sortierung und Duplikat-Check
            unique_lines = sorted(list(set(lines)))
            st.session_state.duplicate_count = len(lines) - len(unique_lines)
            return unique_lines
    return []

def save_streets(streets_list):
    # Radikale Bereinigung: Keine Leerzeilen, kein Duplikat, strikt A-Z
    raw_list = [str(s).strip() for s in streets_list if str(s).strip()]
    cleaned = sorted(list(set(raw_list)))
    st.session_state.duplicate_count = len(raw_list) - len(cleaned)
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.main_list = cleaned

# Session State laden
if 'main_list' not in st.session_state:
    st.session_state.main_list = load_streets()
if 'version_counter' not in st.session_state: st.session_state.version_counter = 0

# --- 3. UI LAYOUT ---
st.title(f"🌐 Integral Dashboard {SERIAL_NUMBER}")

# Bereich A: Input & Pseudo-Liste
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📥 Dateien hochladen (*.txt)")
    up = st.file_uploader("Zieh deine Dateien hierher", type=["txt"], accept_multiple_files=True)
    if up:
        combined_new = []
        for file in up:
            combined_new.extend([s.strip() for s in file.getvalue().decode("utf-8").splitlines() if s.strip()])
        
        # Bestehende Liste + neue Liste
        full_list = st.session_state.main_list + combined_new
        save_streets(full_list)
        st.session_state.version_counter += 1
        st.success(f"Daten verarbeitet! {st.session_state.duplicate_count} Duplikate entfernt.")
        st.rerun()

with col_right:
    st.subheader("📋 Pseudo-Straßenliste (Sortiert A-Z)")
    # Die "Reintext-Vorschau" für den schnellen Check
    clean_text = "\n".join(st.session_state.main_list)
    st.text_area("Vorschau der Namen in den Dateien", value=clean_text, height=200, key="preview_area")
    if st.session_state.duplicate_count > 0:
        st.warning(f"ℹ️ Hinweis: {st.session_state.duplicate_count} doppelte Einträge wurden automatisch bereinigt.")

st.markdown("---")

# Bereich B: Interaktiver Editor
st.subheader(f"🛠️ Korrektur der Straßennamen ({len(st.session_state.main_list)} Unikate)")

df_display = pd.DataFrame(st.session_state.main_list, columns=["Bereinigte Namen"])
edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_v{st.session_state.version_counter}"
)

if not edited_df.equals(df_display):
    save_streets(edited_df["Bereinigte Namen"].tolist())
    st.rerun()

# Bereich C: Footer Buttons
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.info(f"Route wird ab {START_ADRESSE} berechnet...")
with c2:
    st.download_button("💾 BEREINIGTE LISTE LADEN", data="\n".join(st.session_state.main_list), file_name="saubere_liste.txt", use_container_width=True)
with c3:
    if st.button("🚨 ALLES LÖSCHEN", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.main_list = []
        st.session_state.duplicate_count = 0
        st.rerun()
