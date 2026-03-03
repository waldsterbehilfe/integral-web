import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-067" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

# Pfad zur Datei
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 2. FUNKTIONEN (SORTIERUNG & SPEICHERN) ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            # Direkt beim Laden sortieren (A-Z)
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return sorted(list(set(lines)))
    return []

def save_streets(streets_list):
    # Bereinigen und Sortieren vor dem Speichern
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.saved_manual_streets = cleaned

# Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()

# --- 3. UI ---
st.title(f"📍 Straßenverwaltung {SERIAL_NUMBER}")

# Import Bereich (Drag & Drop + Datei)
with st.expander("📥 Neue Liste laden (TXT)", expanded=len(st.session_state.saved_manual_streets) == 0):
    up = st.file_uploader("Zieh deine *.txt Datei hierher oder klicke zum Auswählen", type=["txt"])
    if up:
        new_content = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        # Kombiniere alte und neue Daten, sortiere sie
        combined = st.session_state.saved_manual_streets + new_content
        save_streets(combined)
        st.success(f"{len(new_content)} Einträge geladen und alphabetisch einsortiert!")
        st.rerun()

st.markdown("---")

# Editor Bereich
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)} Einträge)")
st.info("Du kannst direkt in die Zellen klicken, um Hausnummern zu ergänzen oder Fehler zu korrigieren. Neue Zeilen am Ende hinzufügen ist ebenfalls möglich.")

# Wir nutzen ein DataFrame für die komfortable Bearbeitung
df_display = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])

# Der Editor mit dynamischen Zeilen
edited_df = st.data_editor(
    df_display, 
    num_rows="dynamic", 
    use_container_width=True, 
    key="streets_editor_v67"
)

# Überprüfung auf Änderungen & Automatisches Sortieren nach Korrektur
if not edited_df.equals(df_display):
    # Wenn der Nutzer fertig ist mit Tippen, sortieren wir neu und speichern
    save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
    st.rerun()

# Steuerung
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.write("Analyse wird vorbereitet...")
with col_btn2:
    if st.button("🚨 LISTE LEEREN"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.rerun()
