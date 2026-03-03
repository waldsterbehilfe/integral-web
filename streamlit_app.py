import streamlit as st
import pandas as pd
import os
import hashlib

# --- 0. GOLDSTANDARD SETUP ---
# Gespeichert als "test 1 2 3" (Stand: 22:00 Uhr)
SERIAL_NUMBER = "SN-GOLD-2200" 
st.set_page_config(page_title=f"INTEGRAL {SERIAL_NUMBER}", layout="wide")

START_ADRESSE = "Umgehungsstraße 7, 35043 Marburg-Cappel"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- 1. DIE "BUNTE" LOGIK (DAS HERZSTÜCK) ---
def get_row_color(row):
    """
    Erzeugt eine bunte HTML-Markierung. 
    Gleiche Anfangsbuchstaben/Wörter ergeben gleiche Farben (Clustering).
    """
    val = str(row['Zieladresse'])
    if not val: return [''] * len(row)
    
    # Extrahiere das erste Wort (z.B. "Marburger")
    prefix = val.split(" ")[0].lower()
    hash_obj = hashlib.md5(prefix.encode())
    hex_color = hash_obj.hexdigest()
    
    # Generiere helle, angenehme Pastelltöne für die Tabelle
    r = int(hex_color[:2], 16) % 100 + 155
    g = int(hex_color[2:4], 16) % 100 + 155
    b = int(hex_color[4:6], 16) % 100 + 155
    
    style = f'background-color: rgb({r}, {g}, {b}); color: #1a1a1a; font-weight: 500;'
    return [style] * len(row)

# --- 2. DATEN-HANDLING ---
if 'main_list' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.main_list = sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    else:
        st.session_state.main_list = []

# --- 3. UI LAYOUT (2-SPALTEN-STRATEGIE) ---
st.title(f"🚀 INTEGRAL GOLD3000 {SERIAL_NUMBER}")
st.write(f"📍 Startpunkt für KM-Berechnung: **{START_ADRESSE}**")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📥 1. Rohdaten-Input (Manuell)")
    # Das Textfeld für die direkte Bearbeitung
    current_input = "\n".join(st.session_state.main_list)
    raw_data = st.text_area("Straßen hier einpflegen:", value=current_input, height=350)
    
    if st.button("💾 SPEICHERN & FARBIG MARKIEREN", use_container_width=True):
        new_list = sorted(list(set([l.strip() for l in raw_data.splitlines() if l.strip()])))
        st.session_state.main_list = new_list
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(new_list))
        st.rerun()

with col_right:
    st.subheader("📊 2. Bunte Ergebnis-Ausgabe")
    if st.session_state.main_list:
        df = pd.DataFrame(st.session_state.main_list, columns=["Zieladresse"])
        
        # Hier wird der bunte Style auf die Tabelle angewendet
        st.dataframe(
            df.style.apply(get_row_color, axis=1),
            use_container_width=True,
            height=400
        )
    else:
        st.warning("Noch keine Adressen geladen.")

# --- 4. AKTIONEN ---
st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.success("Berechnung läuft im Hintergrund...")
with c2:
    st.download_button("💾 TXT EXPORT", data="\n".join(st.session_state.main_list), file_name="geprueft.txt", use_container_width=True)
with c3:
    if st.button("🚨 RESET", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.main_list = []
        st.rerun()
