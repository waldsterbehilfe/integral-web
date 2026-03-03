import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-076" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

# Festgelegter Startpunkt
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

# --- 2. HILFSFUNKTIONEN ---
def sync_to_disk():
    st.session_state.main_list = sorted(list(set([str(s).strip() for s in st.session_state.main_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(st.session_state.main_list))

# --- 3. UI LAYOUT ---
st.title(f"🌐 Integral Dashboard {SERIAL_NUMBER}")

# Bereich A: Input & Pseudo-Liste (Vorschau)
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📥 Daten-Input")
    up = st.file_uploader("Datei hierher ziehen (TXT)", type=["txt"])
    if up:
        new_lines = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        st.session_state.main_list = list(set(st.session_state.main_list + new_lines))
        st.session_state.version_counter += 1
        sync_to_disk()
        st.rerun()
    
    new_val = st.text_input("Einzelne Straße hinzufügen")
    if st.button("Hinzufügen"):
        if new_val:
            st.session_state.main_list.append(new_val)
            st.session_state.version_counter += 1
            sync_to_disk()
            st.rerun()

with col_right:
    st.subheader("📋 Pseudo-Straßenliste (Vorschau)")
    # Ein scrollbares Textfeld, das den aktuellen Inhalt der Liste zeigt
    vorschau_text = "\n".join(st.session_state.main_list)
    st.text_area("Rohdaten-Ansicht", value=vorschau_text, height=180, help="Das ist der Inhalt der geladenen Dateien.")

st.markdown("---")

# Bereich B: Die interaktive Bearbeitung
st.subheader(f"🛠️ Korrektur & Bearbeitung ({len(st.session_state.main_list)} Einträge)")

df_display = pd.DataFrame(st.session_state.main_list, columns=["Adresse (Strasse | Nr)"])

# Der Editor für Korrekturen (Hausnummern etc.)
edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_v{st.session_state.version_counter}"
)

if not edited_df.equals(df_display):
    st.session_state.main_list = edited_df["Adresse (Strasse | Nr)"].tolist()
    sync_to_disk()
    st.rerun() # Sofort-Update der Pseudo-Liste rechts

# Bereich C: Steuerung
st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 ANALYSE STARTEN (ab Umgehungsstr. 7)", type="primary", use_container_width=True):
        st.info("Berechnung startet...")
with c2:
    # Export-Funktion falls gewünscht
    st.download_button("💾 LISTE EXPORTIEREN", data="\n".join(st.session_state.main_list), file_name="gepruefte_strassen.txt", use_container_width=True)
with c3:
    if st.button("🚨 ALLES LÖSCHEN", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.main_list = []
        st.session_state.version_counter += 1
        st.rerun()
