import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-068" 

# --- 1. SETUP ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 2. LOGIK ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return sorted(list(set(lines)))
    return []

def save_streets(streets_list):
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    # State sofort aktualisieren!
    st.session_state.saved_manual_streets = cleaned

# Initialisierung des Session States beim ersten Start
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()

# --- 3. UI ---
st.title(f"📍 Straßenverwaltung {SERIAL_NUMBER}")

with st.expander("📥 Neue Liste laden (TXT)", expanded=not st.session_state.saved_manual_streets):
    up = st.file_uploader("Zieh deine *.txt Datei hierher", type=["txt"])
    if up:
        new_content = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        combined = list(set(st.session_state.saved_manual_streets + new_content))
        save_streets(combined)
        st.success(f"{len(new_content)} Einträge geladen!")
        st.rerun() # App neu zeichnen, um Liste anzuzeigen

st.markdown("---")

# Der Editor-Teil
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)} Einträge)")

# Falls der State leer ist, aber die Datei Daten hat -> Not-Sync
if not st.session_state.saved_manual_streets:
    st.session_state.saved_manual_streets = load_streets()

# WICHTIG: Wir übergeben die Liste direkt als DataFrame
df_init = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])

# Editor mit eindeutigem Key
edited_df = st.data_editor(
    df_init, 
    num_rows="dynamic", 
    use_container_width=True, 
    key=f"editor_{len(st.session_state.saved_manual_streets)}" # Key ändert sich bei Datenänderung -> Force Refresh
)

# Speichern bei Änderungen
if not edited_df.equals(df_init):
    save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
    st.rerun()

# --- FOOTER ---
if st.button("🚨 LISTE KOMPLETT LEEREN"):
    if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
    st.session_state.saved_manual_streets = []
    st.rerun()
