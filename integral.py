import folium
import osmnx as ox
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import threading
import shutil
import json
import sys
from datetime import datetime
from collections import defaultdict

# --- PFAD-LOGIK FÜR EXE-BETRIEB ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

HINTERGRUND_BILD = resource_path("hintergrund.png")

# --- INITIALISIERUNG ---
root = tk.Tk()
root.withdraw()

def create_splash(parent):
    splash = tk.Toplevel(parent)
    splash.overrideredirect(True)
    splash.geometry("300x150")
    sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
    splash.geometry(f"+{(sw//2)-150}+{(sh//2)-75}")
    canvas = tk.Canvas(splash, width=300, height=150, bg="white", highlightthickness=1, highlightbackground="lightgray")
    canvas.pack()
    canvas.create_text(150, 50, text="INTEGRAL", font=("Arial", 18, "bold"), fill="#2c3e50")
    canvas.create_text(150, 80, text="Sortiere nach Ortsteilen...", font=("Arial", 10))
    pb = ttk.Progressbar(splash, orient="horizontal", length=200, mode="indeterminate")
    pb.place(x=50, y=110)
    pb.start(15)
    splash.update()
    return splash

temp_splash = create_splash(root)

CACHE_DIR = "geocache"
CONFIG_FILE = "config.json"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)

ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

class IntegralApp:
    def __init__(self, root, splash_to_destroy):
        self.root = root
        self.splash = splash_to_destroy
        self.root.title("INTEGRAL")
        self.root.geometry("500x320")
        self.root.resizable(False, False)
        
        self.stopp_flag = False
        self.is_running = False 
        self.history = []
        self.errors = [] 
        self.last_path = ""
        self.load_config()

        self.colors = {
            "light": {"bg": "white", "fg": "#2c3e50", "status": "darkblue", "btn_start": "#e3f2fd"},
            "dark": {"bg": "#2b2b2b", "fg": "#ffffff", "status": "#3498db", "btn_start": "#1976d2"}
        }

        # Menü
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        self.history_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Verlauf", menu=self.history_menu)
        self.error_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Fehler-Log (0)", menu=self.error_menu)
        
        self.update_history_menu()
        self.update_error_menu()

        # UI Elemente
        self.bg_label = tk.Label(root)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_photo = None
        self.load_bg_image()

        self.title_label = tk.Label(root, text="Kartengenerator", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=(20, 0))
        self.label_status = tk.Label(root, text="Bereit", font=("Arial", 11))
        self.label_status.pack(pady=(60, 0))
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        
        self.btn_start = tk.Button(root, text="Datei wählen & Starten", command=self.start_click, 
                                   height=2, width=28, font=("Arial", 10, "bold"), relief="raised", bd=2)
        self.btn_start.pack(pady=(20, 10))
        self.btn_abbruch = tk.Button(root, text="Abbruch", command=self.stop_process, 
                                     bg="#f8d7da", fg="#c0392b", font=("Arial", 10, "bold"))

        self.btn_bg_toggle = tk.Button(root, text="⧉", command=self.toggle_bg, font=("Arial", 9), bd=0, cursor="hand2")
        self.btn_bg_toggle.place(relx=0.955, rely=0.01, anchor="ne")
        
        self.btn_mode = tk.Button(root, text="☾", command=self.toggle_mode, font=("Arial", 9), bd=0, cursor="hand2")
        self.btn_mode.place(relx=0.99, rely=0.01, anchor="ne")

        self.label_cache_count = tk.Label(root, text="", font=("Arial", 7), fg="gray")
        self.label_cache_count.place(relx=0.02, rely=0.88, anchor="sw")
        
        self.branding = tk.Label(root, text="© Maus", font=("Arial", 8, "italic"), fg="gray")
        self.branding.place(relx=0.98, rely=0.97, anchor="se")
        
        self.update_ui_colors()
        self.update_cache_display()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(2000, self.finish_splash)

    def log_error(self, message):
        self.errors.append(f"[{datetime.now().strftime('%H:%M')}] {message}")
        self.update_error_menu()

    def update_error_menu(self):
        self.error_menu.delete(0, tk.END)
        self.menubar.entryconfig(2, label=f"Fehler-Log ({len(self.errors)})")
        for err in reversed(self.errors[-10:]): self.error_menu.add_command(label=err, state="disabled")

    def update_history_menu(self):
        self.history_menu.delete(0, tk.END)
        valid = [p for p in self.history if os.path.exists(p)]
        for path in valid[:5]: 
            self.history_menu.add_command(label=f"Öffnen: {os.path.basename(path)}", command=lambda p=path: os.startfile(p))

    def add_to_history(self, path):
        abs_p = os.path.abspath(path)
        if abs_p in self.history: self.history.remove(abs_p)
        self.history.insert(0, abs_p); self.history = self.history[:5]
        self.update_history_menu(); self.save_config()

    def stop_process(self): self.stopp_flag = True

    def start_click(self):
        pfad = filedialog.askopenfilename(filetypes=[("Textdateien", "*.txt")])
        if pfad:
            self.last_path = pfad
            self.stopp_flag = False
            self.is_running = True
            self.btn_start.pack_forget()
            self.btn_abbruch.pack(pady=(20, 10))
            self.progress.pack(pady=5)
            threading.Thread(target=self.verarbeitung, args=(pfad,), daemon=True).start()

    def verarbeitung(self, dateipfad):
        try:
            # Daten-Struktur: { "Ort/Ortsteil": [Liste von GeoJSON-Elementen] }
            ort_sammlung = defaultdict(list)
            
            with open(dateipfad, 'r', encoding='utf-8') as f:
                strassen = [s.strip() for s in f if s.strip()]
            
            total = len(strassen)
            self.progress["maximum"] = total
            gefundene_gesamt = 0

            for i, strasse in enumerate(strassen):
                if self.stopp_flag: break
                self.label_status.config(text=f"Suche: {strasse} ({i+1}/{total})")
                
                try:
                    # Suche im Landkreis Marburg-Biedenkopf
                    query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                        gdf_f = gdf[gdf['name'].str.contains(strasse, case=False, na=False)] if 'name' in gdf.columns else gdf
                        
                        if not gdf_f.empty:
                            # --- ORTS-ERKENNUNG ---
                            stadt_info = "Unbekannter_Ort"
                            for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                                if col in gdf_f.columns and gdf_f[col].dropna().any():
                                    stadt_info = gdf_f[col].dropna().iloc[0]
                                    break
                            
                            style = {'color':'red','weight':6,'opacity':0.8}
                            geo_data = folium.GeoJson(gdf_f, style_function=lambda x, s=style: s, tooltip=strasse)
                            ort_sammlung[stadt_info].append(geo_data)
                            gefundene_gesamt += 1
                        else: self.log_error(f"Nicht eindeutig: {strasse}")
                    else: self.log_error(f"Fehlt: {strasse}")
                except: self.log_error(f"Fehler: {strasse}")
                
                self.progress["value"] = i + 1
                self.root.update_idletasks()

            # --- HTML-DATEIEN FÜR JEDEN GEFUNDENEN ORT ERSTELLEN ---
            if gefundene_gesamt > 0 and not self.stopp_flag:
                zeit = datetime.now().strftime("%H%M")
                ausgabe_ordner = f"Karten_{zeit}"
                if not os.path.exists(ausgabe_ordner): os.makedirs(ausgabe_ordner)

                for ort, elemente in ort_sammlung.items():
                    # Karte zentrieren (Beispiel Amöneburg/Marburg)
                    temp_karte = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente: el.add_to(temp_karte)
                    
                    safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                    dateiname = os.path.abspath(os.path.join(ausgabe_ordner, f"Karte_{safe_ort}.html"))
                    temp_karte.save(dateiname)
                    self.add_to_history(dateiname)

                os.startfile(os.path.abspath(ausgabe_ordner))
                self.label_status.config(text=f"Fertig! {len(ort_sammlung)} Orte erstellt.")
            else:
                self.label_status.config(text="Beendet (Nichts gefunden)")

        except Exception as e: self.log_error(f"System: {str(e)}")
        finally:
            self.is_running = False
            self.ui_reset()

    def ui_reset(self):
        self.btn_abbruch.pack_forget(); self.progress.pack_forget()
        self.btn_start.pack(pady=(20, 10)); self.update_cache_display()

    def finish_splash(self): 
        if self.splash: self.splash.destroy()
        self.root.deiconify()

    def load_bg_image(self):
        if os.path.exists(HINTERGRUND_BILD):
            img = Image.open(HINTERGRUND_BILD).resize((500, 320), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(img, master=self.root)

    def load_config(self):
        self.dark_mode, self.bg_visible, self.history = False, True, []
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    d = json.load(f); self.dark_mode = d.get("dark_mode", False)
                    self.bg_visible = d.get("bg_visible", True)
                    self.history = d.get("history", [])
            except: pass

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"dark_mode": self.dark_mode, "bg_visible": self.bg_visible, "history": self.history}, f)

    def on_closing(self): self.save_config(); self.root.destroy()
    def toggle_bg(self): self.bg_visible = not self.bg_visible; self.update_ui_colors()
    def toggle_mode(self): self.dark_mode = not self.dark_mode; self.update_ui_colors()

    def update_ui_colors(self):
        m = "dark" if self.dark_mode else "light"
        c = self.colors[m]; label_bg = c["bg"]
        if self.bg_visible and self.bg_photo:
            self.bg_label.config(image=self.bg_photo)
            label_bg = "white" if not self.dark_mode else "#2b2b2b"
        else: self.bg_label.config(image="", bg=c["bg"])
        for w in [self.title_label, self.label_status, self.label_cache_count, self.branding, self.btn_mode, self.btn_bg_toggle]:
            w.config(bg=label_bg, fg=c["fg"] if w != self.label_status else c["status"], bd=0)
        self.btn_start.config(bg=c["btn_start"], fg="black" if not self.dark_mode else "white")
        self.btn_mode.config(text="☼" if self.dark_mode else "☾")

    def update_cache_display(self):
        count = sum([len(files) for r, d, files in os.walk(CACHE_DIR)])
        self.label_cache_count.config(text=f"Cache: {count} Einträge")

if __name__ == "__main__":
    app = IntegralApp(root, temp_splash)
    root.mainloop()