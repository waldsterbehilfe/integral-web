import streamlit as st
import pandas as pd
import os

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-071" 

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
st.title(f"📍 Integral Dashboard {SERIAL_NUMBER}")

# Import Bereich
with st.expander("📥 TXT-Import & Einzel-Eingabe", expanded=not st.session_state.saved_manual_streets):
    c1, c2 = st.columns([2, 1])
    with c1:
        up = st.file_uploader("Datei wählen oder Drag&Drop", type=["txt"])
        if up:
            new_content = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
            # FIX: Wir löschen den Editor-State im Hintergrund, damit er sich neu aufbauen MUSS
            if "streets_editor" in st.session_state:
                del st.session_state["streets_editor"]
            save_streets(st.session_state.saved_manual_streets + new_content)
            st.rerun()

    with c2:
        new_entry = st.text_input("Einzelne Straße hinzufügen")
        if st.button("Hinzufügen"):
            if new_entry:
                if "streets_editor" in st.session_state:
                    del st.session_state["streets_editor"]
                save_streets(st.session_state.saved_manual_streets + [new_entry])
                st.rerun()

st.markdown("---")

# Die Tabelle - JETZT STABIL
st.subheader(f"📝 Aktuelle Straßenliste ({len(st.session_state.saved_manual_streets)})")

# Wir nutzen eine Kopie der Daten für den Editor
df_editor = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])

# Der Editor ohne komplexen Key-Schnickschnack, aber mit manuellem State-Reset (siehe oben)
edited_df = st.data_editor(
    df_editor, 
    num_rows="dynamic", 
    use_container_width=True, 
    key="streets_editor"
)

# Speichern nur, wenn sich wirklich der Inhalt geändert hat
if not edited_df.equals(df_editor):
    save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
    st.rerun()

# Reset Button
if st.button("🚨 LISTE LEEREN"):
    if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
    if "streets_editor" in st.session_state:
        del st.session_state["streets_editor"]
    st.session_state.saved_manual_streets = []
    st.rerun()
