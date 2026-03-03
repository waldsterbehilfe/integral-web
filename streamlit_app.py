import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-070" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 2. LOGIK ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return sorted(list(set(lines))) # Immer sortiert zurückgeben
    return []

def save_streets(streets_list):
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.saved_manual_streets = cleaned

# Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# --- 3. UI ---
st.title(f"🚀 Integral Dashboard {SERIAL_NUMBER}")

# Import & Einzel-Eingabe
c1, c2 = st.columns([2, 1])
with c1:
    with st.expander("📥 TXT-Import (Drag & Drop)"):
        up = st.file_uploader("Datei wählen", type=["txt"], key="file_up")
        if up:
            new_content = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            save_streets(st.session_state.saved_manual_streets + new_content)
            st.rerun()

with c2:
    with st.expander("➕ Schnell-Eingabe", expanded=True):
        new_entry = st.text_input("Straße & Hausnummer", key="manual_in", placeholder="Musterstr. 1")
        if st.button("Hinzufügen"):
            if new_entry:
                save_streets(st.session_state.saved_manual_streets + [new_entry])
                st.rerun()

st.markdown("---")

# Die Tabelle
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)})")

if st.session_state.saved_manual_streets:
    df_active = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    
    # Dynamischer Key für Refresh-Garantie
    editor_key = f"ed_v70_{len(st.session_state.saved_manual_streets)}"
    
    edited_df = st.data_editor(df_active, num_rows="dynamic", use_container_width=True, key=editor_key)

    if not edited_df.equals(df_active):
        save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
        st.rerun()

    # Analyse Bereich
    st.markdown("### 📊 Auswertung")
    ca, cb = st.columns(2)
    with ca:
        if st.button("🚀 ANALYSE STARTEN", type="primary"):
            # Simulation der Berechnung für die KM
            # In der nächsten Version binden wir hier wieder OSMnx ein
            st.session_state.analysis_results = {"status": "ready"}
    with cb:
        if st.button("🗑️ LISTE LEEREN"):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.session_state.analysis_results = None
            st.rerun()

    if st.session_state.analysis_results:
        st.info("Analyse-Modul bereit. Soll ich die echten Geodaten für diese Liste laden?")
else:
    st.info("Warte auf Daten-Input...")
