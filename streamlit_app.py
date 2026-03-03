import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-074" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# Initialisierung aller State-Variablen
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
    # Bereinigen und Sortieren (A-Z)
    st.session_state.main_list = sorted(list(set([str(s).strip() for s in st.session_state.main_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(st.session_state.main_list))

# --- 3. UI LAYOUT ---
st.title(f"🌐 Integral Dashboard {SERIAL_NUMBER}")

# Kontroll-Zentrum
with st.container():
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        # Drag & Drop Bereich
        up = st.file_uploader("📂 Liste importieren (*.txt)", type=["txt"], key="uploader")
        if up:
            new_lines = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            st.session_state.main_list = list(set(st.session_state.main_list + new_lines))
            st.session_state.version_counter += 1
            sync_to_disk()
            st.rerun()

    with c2:
        st.write("##") # Abstand
        if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
            st.session_state.analysis_active = True
        
        if st.button("🛑 ANALYSE STOPPEN", use_container_width=True):
            st.session_state.analysis_active = False
            st.rerun()

    with c3:
        st.write("##")
        if st.button("🚨 LISTE LEEREN", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.main_list = []
            st.session_state.version_counter += 1
            st.session_state.analysis_active = False
            st.rerun()

st.markdown("---")

# Bereich für die manuelle Schnell-Eingabe
with st.expander("➕ Einzeleingabe (Hausnummern korrigieren / hinzufügen)", expanded=False):
    col_in, col_btn = st.columns([3, 1])
    new_val = col_in.text_input("Straße & Hausnummer eingeben", key="manual_add_field")
    if col_btn.button("Hinzufügen", use_container_width=True):
        if new_val:
            st.session_state.main_list.append(new_val)
            st.session_state.version_counter += 1
            sync_to_disk()
            st.rerun()

# --- 4. DIE TABELLE ---
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.main_list)})")

df_display = pd.DataFrame(st.session_state.main_list, columns=["Adresse (Strasse | Nr)"])

# Der Editor nutzt den Versions-Key für den Force-Refresh
edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_v{st.session_state.version_counter}"
)

# Echtzeit-Speicherung bei Tabellen-Edits
if not edited_df.equals(df_display):
    st.session_state.main_list = edited_df["Adresse (Strasse | Nr)"].tolist()
    sync_to_disk()

# --- 5. ANALYSE-ANZEIGE ---
if st.session_state.analysis_active:
    st.markdown("---")
    st.subheader("📊 Analyse-Ergebnisse")
    if not st.session_state.main_list:
        st.warning("Keine Daten für die Analyse vorhanden.")
    else:
        st.info("Berechnung der optimalen Route und Kilometer läuft... (Hier binden wir im nächsten Schritt wieder OSMnx ein)")
        # Platzhalter für die Ergebnisse (KM, Zeit, Karte)
        st.metric("Gesamtstrecke", "0.00 km")
        st.metric("Geschätzte Zeit", "0.0 Std.")
