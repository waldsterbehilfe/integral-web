import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-069" 

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
    st.session_state.saved_manual_streets = cleaned

# Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()

# --- 3. UI ---
st.title(f"📍 Echtzeit-Straßenverwaltung {SERIAL_NUMBER}")

# Bereich A: Import & Manuelle Eingabe
c1, c2 = st.columns([2, 1])

with c1:
    with st.expander("📥 TXT-Import (Drag & Drop)", expanded=not st.session_state.saved_manual_streets):
        up = st.file_uploader("Datei wählen", type=["txt"], key="file_up")
        if up:
            new_content = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            combined = st.session_state.saved_manual_streets + new_content
            save_streets(combined)
            st.rerun()

with c2:
    with st.expander("➕ Einzelne Straße", expanded=True):
        new_entry = st.text_input("Name & Hausnummer", key="manual_in")
        if st.button("Hinzufügen"):
            if new_entry:
                save_streets(st.session_state.saved_manual_streets + [new_entry])
                st.rerun()

st.markdown("---")

# Bereich B: Die Liste (Das Herzstück)
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)})")

if st.session_state.saved_manual_streets:
    # Wir erstellen ein frisches DF
    df_active = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    
    # Der Trick: Wir geben dem Editor einen Key, der sich ändert, wenn wir speichern
    # So wird die Tabelle IMMER neu gezeichnet
    editor_key = f"editor_state_{len(st.session_state.saved_manual_streets)}"
    
    edited_df = st.data_editor(
        df_active,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key
    )

    # Speichern wenn User in der Tabelle editiert
    if not edited_df.equals(df_active):
        save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
        st.rerun()
else:
    st.warning("Die Liste ist aktuell leer. Nutze den Import oder die Einzeleingabe oben.")

# Bereich C: Aktionen
if st.session_state.saved_manual_streets:
    if st.button("🗑️ ALLES LÖSCHEN"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.rerun()
