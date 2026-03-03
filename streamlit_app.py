import streamlit as st
import pandas as pd
import os
import hashlib

# --- 0. SETUP ---
SERIAL_NUMBER = "SN-085"
st.set_page_config(page_title=f"INTEGRAL COLOR-DASH {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 1. FARB-GENERATOR (Die bunte Magie) ---
def get_color_from_text(text):
    """Erzeugt eine konsistente Hintergrundfarbe basierend auf dem Straßennamen."""
    if not text: return ""
    # Wir nehmen den ersten Teil des Namens für die Farbgruppe
    base = text.split(" ")[0].lower()
    # Generiere einen Hash-Wert für eine stabile Farbe
    hash_object = hashlib.md5(base.encode())
    hex_hash = hash_object.hexdigest()
    
    # Erzeuge helle Pastelltöne (damit man den Text noch lesen kann)
    r = int(hex_hash[:2], 16) % 64 + 190
    g = int(hex_hash[2:4], 16) % 64 + 190
    b = int(hex_hash[4:6], 16) % 64 + 190
    return f'background-color: rgb({r}, {g}, {b}); color: black;'

def style_dataframe(df):
    """Wendet die Farben auf die gesamte Spalte an."""
    return df.style.map(get_color_from_text, subset=['Zieladresse'])

# --- 2. DATEN-LOGIK ---
if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    else:
        st.session_state.main_list = []

# --- 3. UI ---
st.title(f"🌈 Integral Color-Dashboard {SERIAL_NUMBER}")

c_in, c_preview = st.columns([1, 1])

with c_in:
    st.subheader("📥 Input")
    raw_input = st.text_area("Straßenliste editieren:", 
                             value="\n".join(st.session_state.main_list), 
                             height=300)
    if st.button("💾 SPEICHERN & FARBEN AKTUALISIEREN"):
        new_list = sorted(list(set([l.strip() for l in raw_input.splitlines() if l.strip()])))
        st.session_state.main_list = new_list
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(new_list))
        st.rerun()

with c_preview:
    st.subheader("📊 Bunte Analyse-Vorschau")
    if st.session_state.main_list:
        df = pd.DataFrame(st.session_state.main_list, columns=["Zieladresse"])
        # Das Styling wird hier "gebacken"
        st.dataframe(style_dataframe(df), use_container_width=True, height=340)
    else:
        st.info("Noch keine Daten vorhanden.")

st.markdown("---")

# --- 4. DER INTERAKTIVE EDITOR (BUNT) ---
st.subheader("🛠️ Interaktive Korrektur")
if st.session_state.main_list:
    df_editor = pd.DataFrame(st.session_state.main_list, columns=["Zieladresse"])
    # Hinweis: Im data_editor ist komplexes Styling oft eingeschränkt, 
    # daher nutzen wir hier die saubere Anzeige-Variante von oben für die Farben.
    edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="col_editor")
    
    if not edited_df.equals(df_editor):
        st.session_state.main_list = sorted(list(set(edited_df["Zieladresse"].tolist())))
        st.rerun()
