import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-072" 

# --- 1. SETUP & DATEI-CHECK ---
st.set_page_config(page_title=f"INTEGRAL {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

def load_from_file():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

def save_to_file(data_list):
    cleaned = sorted(list(set([str(s).strip() for s in data_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    return cleaned

# --- 2. SESSION STATE INITIALISIERUNG ---
# Wir laden die Daten EINMALIG in den State beim Start
if 'main_list' not in st.session_state:
    st.session_state.main_list = load_from_file()

# --- 3. UI HEADER ---
st.title(f"📍 Integral Dashboard {SERIAL_NUMBER}")

# Import & Einzel-Eingabe in einem kompakten Block
with st.container():
    c1, c2 = st.columns([2, 1])
    with c1:
        up = st.file_uploader("Datei laden (Drag & Drop)", type=["txt"], key="uploader")
        if up:
            new_lines = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            # Update State & Datei
            st.session_state.main_list = save_to_file(st.session_state.main_list + new_lines)
            st.rerun()
    with c2:
        new_val = st.text_input("Manuelle Eingabe", placeholder="Straße 123", key="manual_add")
        if st.button("➕ Hinzufügen") and new_val:
            st.session_state.main_list = save_to_file(st.session_state.main_list + [new_val])
            st.rerun()

st.markdown("---")

# --- 4. DER TABELLEN-EDITOR (DER KRITISCHE TEIL) ---
st.subheader(f"📝 Aktuelle Liste ({len(st.session_state.main_list)})")

# Wir bauen das DataFrame direkt aus dem State
df = pd.DataFrame(st.session_state.main_list, columns=["Adresse (Strasse | Nr)"])

# Wir nutzen KEINEN festen Key für den Editor, damit er bei jedem rerun() 
# mit den Daten aus 'df' neu initialisiert wird.
edited_df = st.data_editor(
    df, 
    num_rows="dynamic", 
    use_container_width=True,
    key=f"editor_v72_{len(st.session_state.main_list)}" # Trick: Key ändert sich bei Längenänderung
)

# Prüfen auf manuelle Änderungen in der Tabelle
if not edited_df.equals(df):
    st.session_state.main_list = save_to_file(edited_df["Adresse (Strasse | Nr)"].tolist())
    st.rerun()

# --- 5. AKTIONEN ---
st.write("##")
col_a, col_b = st.columns(2)
with col_a:
    if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.success("Analyse bereit. (Geodaten-Modul folgt im nächsten Schritt)")
with col_b:
    if st.button("🚨 LISTE LEEREN", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.main_list = []
        st.rerun()
