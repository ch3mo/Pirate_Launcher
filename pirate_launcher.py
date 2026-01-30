import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import json
import os
import subprocess
import sys
import requests
import threading
from PIL import Image, ImageTk
from io import BytesIO
from urllib.parse import quote
from datetime import datetime, timedelta
import queue
import logging
import psutil
import time
import webbrowser

DIR_NAME = "Pirate Launcher Components"
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
DIR = os.path.join(BASE_DIR, DIR_NAME)
IMG = os.path.join(DIR, "images")
os.makedirs(DIR, exist_ok=True)
os.makedirs(IMG, exist_ok=True)

PLACE = os.path.join(IMG, "no.png")
STEAM_ICON = os.path.join(IMG, "steam_icon_24.png")
XBOX_ICON = os.path.join(IMG, "xbox_icon_24.png")
PIRATE_ICON = os.path.join(IMG, "pirate_icon_24.png")
STAR_PLACE = os.path.join(IMG, "star.png")
STAR_EMPTY = os.path.join(IMG, "star_empty.png")

def safe_create_image(size, color, path, mode='RGB'):
    if os.path.exists(path):
        return
    try:
        img = Image.new(mode, size, color)
        img.save(path)
    except Exception as e:
        print(f"Failed to create {os.path.basename(path)}: {e}")

safe_create_image((480, 640), (50, 50, 50), PLACE)
safe_create_image((20, 20), (255, 215, 0), STAR_PLACE)
safe_create_image((20, 20), (0, 0, 0, 0), STAR_EMPTY, mode='RGBA')

PATHS = {
    "pirated": BASE_DIR,
    "steam": r"C:\Program Files (x86)\Steam\steamapps\common",
    "xbox": r"C:\XboxGames"
}

class Toast:
    def __init__(self, master, message, duration=3500):
        self.toast = tk.Toplevel(master)
        self.toast.wm_overrideredirect(True)
        self.toast.attributes('-topmost', True)
        self.toast.attributes('-alpha', 0.88)
        self.toast.config(bg="#0f0f0f")

        container = tk.Frame(self.toast, bg="#0f0f0f")
        container.pack(padx=14, pady=10)

        self.label = tk.Label(
            container,
            text=message,
            bg="#0f0f0f",
            fg="#eeeeee",
            font=("Segoe UI", 11),
            justify="left",
            wraplength=480
        )
        self.label.pack()

        self.toast.update_idletasks()

        req_width = self.label.winfo_reqwidth() + 48
        req_height = self.label.winfo_reqheight() + 32

        MAX_W = 580
        MAX_H = 220
        final_w = min(max(req_width, 220), MAX_W)
        final_h = min(max(req_height, 54), MAX_H)

        screen_w = self.toast.winfo_screenwidth()
        screen_h = self.toast.winfo_screenheight()

        x = screen_w - final_w - 24
        y = screen_h - final_h - 80

        self.toast.geometry(f"{final_w}x{final_h}+{x}+{y}")

        def fade_out(alpha=0.88):
            if alpha > 0.04:
                self.toast.attributes('-alpha', alpha)
                self.toast.after(60, lambda: fade_out(alpha - 0.06))
            else:
                self.toast.destroy()

        self.toast.after(duration, lambda: fade_out())

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Pirate Launcher")
        self.root.geometry("1950x950")
        self.root.minsize(1650, 800)
        self.root.config(bg="#1e1e1e")
        self.MAIN_BG = "#1e1e1e"
        self.TEXT_BG = "#1e1e1e"
        self.update_queue = queue.Queue()
        self.user = self.load(os.path.join(DIR, "user.json"), "username")
        self.states = {}
        self.games = []
        self.session_status_label = None
        self.overlay_window = None
        self.overlay_running = False
        self.current_game_process = None
        self.active_overlay_game = None
        self.current_game_idx = None
        self.overlay_var = tk.BooleanVar()
        self.last_steamid64 = ""
        self.last_steam_apikey = ""

        if self.user:
            self.load_ui()
        else:
            self.login()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
        self.root.destroy()

    def load(self, fullpath, key=None, default=None):
        if not os.path.exists(fullpath):
            return default
        try:
            with open(fullpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(key) if key else data
        except Exception as e:
            print(f"Load error {fullpath}: {e}")
            return default

    def save(self, fullpath, data):
        try:
            os.makedirs(os.path.dirname(fullpath), exist_ok=True)
            with open(fullpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Save failed {fullpath}: {e}")

    def log(self, msg):
        if hasattr(self, "enable_logging") and self.enable_logging:
            logging.info(f"{datetime.now()}: {msg}")

    def center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def start_title_scroll(self, full_text):
        display_width = 460
        font = ("", 18, "bold")
        temp_canvas = tk.Canvas(self.root)
        temp_id = temp_canvas.create_text(0, 0, text=full_text, font=font, anchor="w")
        text_width = temp_canvas.bbox(temp_id)[2]
        temp_canvas.destroy()
        if text_width <= display_width:
            self.title_canvas.itemconfig(self.title_text_id, text=full_text)
            self.title_canvas.coords(self.title_text_id, 0, 30)
            return
        scrolling_text = full_text + " • " + full_text
        self.title_canvas.itemconfig(self.title_text_id, text=scrolling_text)
        pos = display_width
        scroll_speed = 2
        def animate():
            nonlocal pos
            pos -= scroll_speed
            if pos < -text_width:
                self.root.after(1200, reset)
            else:
                self.title_canvas.coords(self.title_text_id, pos, 30)
                self.root.after(30, animate)
        def reset():
            nonlocal pos
            pos = display_width
            self.title_canvas.coords(self.title_text_id, pos, 30)
            self.root.after(600, animate)
        animate()

    def process_queue(self):
        try:
            while True:
                task = self.update_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def _migrate_games(self):
        changed = False
        for g in self.games:
            if "playtime" not in g or not isinstance(g["playtime"], (int, float)):
                g["playtime"] = 0.0
                changed = True
            if "last_launch" not in g:
                g["last_launch"] = None
                changed = True
            if "favorite" not in g:
                g["favorite"] = False
                changed = True
            if "added_date" not in g:
                g["added_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                changed = True
            if "overlay_enabled" not in g:
                g["overlay_enabled"] = True
                changed = True
            if "steam_imported_seconds" not in g:
                g["steam_imported_seconds"] = 0
                changed = True
        if changed:
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

    def load_ui(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.center_window()

        self.profiles = self.load(os.path.join(DIR, "profiles.json"), default=["Default"])

        settings_path = os.path.join(DIR, "settings.json")
        default_settings = {
            "profile": "Default",
            "auto_refresh": True,
            "show_toast": True,
            "enable_logging": False,
            "recently_played_format": "date_time",
            "last_steamid64": "",
            "last_steam_apikey": ""
        }
        loaded_settings = self.load(settings_path)
        if loaded_settings is None or not isinstance(loaded_settings, dict):
            loaded_settings = {}
        settings = {**default_settings, **loaded_settings}
        self.save(settings_path, settings)

        self.current = settings["profile"]
        self.auto_refresh = settings.get("auto_refresh", True)
        self.show_toast = settings.get("show_toast", True)
        self.enable_logging = settings.get("enable_logging", False)
        self.recent_format = settings.get("recently_played_format", "date_time")
        self.last_steamid64 = settings.get("last_steamid64", "")
        self.last_steam_apikey = settings.get("last_steam_apikey", "")

        if self.enable_logging:
            logging.basicConfig(filename=os.path.join(DIR, "launcher.log"),
                               level=logging.INFO, format="%(asctime)s - %(message)s")

        self.games = self.load(os.path.join(DIR, f"{self.current}_games.json"), default=[])
        self._migrate_games()

        self.states = {
            g["name"]: {"running": False, "start_time": None, "session_duration": timedelta(0)}
            for g in self.games
        }

        self.cache = {}
        self.pending_scrapes = set()
        cache_issues = 0

        for g in self.games:
            name = g["name"]
            cache_file = os.path.join(IMG, f"{name.replace(' ', '_')}_info.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        loaded.setdefault("image", PLACE)
                        loaded.setdefault("title", name)
                        loaded.setdefault("details", "")
                        loaded.setdefault("description", "No description available")
                        loaded.setdefault("appid", None)
                        self.cache[name] = loaded
                    else:
                        cache_issues += 1
                        self.cache[name] = {"image": PLACE, "title": name, "details": "", "description": "Loading... (cache issue)", "appid": None}
                except:
                    cache_issues += 1
                    self.cache[name] = {"image": PLACE, "title": name, "details": "", "description": "Loading... (cache error)", "appid": None}
            else:
                self.cache[name] = {"image": PLACE, "title": name, "details": "", "description": "Loading...", "appid": None}
                if name not in self.pending_scrapes:
                    self.pending_scrapes.add(name)
                    threading.Thread(target=self.scrape_and_cache, args=(name,), daemon=True).start()

        if cache_issues > 0:
            print(f"Found {cache_issues} problematic cache files - using fallbacks.")

        bottom_frame = tk.Frame(self.root, bg="#121212")
        bottom_frame.pack(side="bottom", fill="x")
        self.status = tk.Label(bottom_frame, text="Ready", anchor="w", bg="#121212", fg="#ccc", font=("", 9))
        self.status.pack(side="left", padx=10, pady=4)
        self.session_status_label = tk.Label(bottom_frame, text="", anchor="e", bg="#121212", fg="#ccc", font=("", 9))
        self.session_status_label.pack(side="right", padx=10, pady=4, fill="x", expand=True)

        main = tk.Frame(self.root, bg="#1e1e1e")
        main.pack(fill="both", expand=True, padx=28, pady=(20, 10))

        sidebar = tk.Frame(main, bg="#1e1e1e", width=200)
        sidebar.pack(side="left", fill="y", padx=(0, 18))
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Platforms", bg="#1e1e1e", fg="#fff", font=("", 13, "bold")).pack(pady=(15, 8), padx=12, anchor="w")

        self.platform_filter = tk.StringVar(value="All")
        self.platform_buttons = {}

        ICON_SIZE = 24
        try:
            self.steam_icon = ImageTk.PhotoImage(Image.open(STEAM_ICON).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
            self.xbox_icon = ImageTk.PhotoImage(Image.open(XBOX_ICON).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
            self.pirate_icon = ImageTk.PhotoImage(Image.open(PIRATE_ICON).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
        except Exception as e:
            print("Could not load custom platform icons:", e)
            self.steam_icon = self.xbox_icon = self.pirate_icon = None

        platforms = [
            ("All", None),
            ("Steam", self.steam_icon),
            ("Xbox", self.xbox_icon),
            ("Pirated", self.pirate_icon)
        ]

        for plat, icon in platforms:
            btn = tk.Button(sidebar, text=plat if icon is None else f" {plat}",
                            compound="left" if icon else "center",
                            image=icon if icon else None,
                            anchor="w", relief="flat", padx=12, pady=10,
                            bg="#2a2a2a" if plat == "All" else "#1e1e1e",
                            fg="#ffffff" if plat == "All" else "#dddddd",
                            font=("", 12),
                            activebackground="#505050", activeforeground="#ffffff",
                            command=lambda p=plat: self.set_platform(p))
            btn.pack(fill="x", pady=3, padx=6)
            self.platform_buttons[plat] = btn

        list_frame = tk.Frame(main, bg="#1e1e1e")
        list_frame.pack(side="left", fill="both", expand=True, padx=(0, 18))

        filter_frame = tk.Frame(list_frame, bg="#1e1e1e")
        filter_frame.pack(fill="x", pady=(0, 8))

        tk.Label(filter_frame, text="Search:", bg="#1e1e1e", fg="#fff").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, bg="#2a2a2a", fg="#fff", insertbackground="#fff")
        search_entry.pack(side="left", fill="x", expand=True, padx=(5, 20))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        tk.Label(filter_frame, text="Sort:", bg="#1e1e1e", fg="#fff").pack(side="left")
        self.sort_var = tk.StringVar(value="Name")
        sort_menu = ttk.Combobox(filter_frame, textvariable=self.sort_var,
                                values=["Name", "Recently Played", "Playtime", "Favorites"],
                                state="readonly", width=15)
        sort_menu.pack(side="left", padx=(5, 0))
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        columns = ("name", "platform", "playtime", "favorite", "recent")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Name", command=lambda: self.sort_by_column("name"))
        self.tree.heading("platform", text="Platform", command=lambda: self.sort_by_column("platform"))
        self.tree.heading("playtime", text="Playtime", command=lambda: self.sort_by_column("playtime"))
        self.tree.heading("favorite", text="★", command=lambda: self.sort_by_column("favorite"))
        self.tree.heading("recent", text="Recently Played", command=lambda: self.sort_by_column("recent"))

        self.tree.column("name", width=650, anchor="w")
        self.tree.column("platform", width=110, anchor="center")
        self.tree.column("playtime", width=110, anchor="center")
        self.tree.column("favorite", width=50, anchor="center")
        self.tree.column("recent", width=180, anchor="center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2a2a2a", foreground="#fff",
                        fieldbackground="#2a2a2a", rowheight=42, font=("", 10))
        style.map("Treeview", background=[("selected", "#505050")])

        v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#333", fg="#fff")
        self.context_menu.add_command(label="Toggle Favorite", command=self.toggle_favorite)
        self.context_menu.add_command(label="Toggle Overlay", command=self.toggle_overlay)
        self.context_menu.add_command(label="Refresh Info", command=self.refresh_selected_info)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Remove", command=self.remove)

        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind("<Up>", self._on_arrow_up)
        self.tree.bind("<Down>", self._on_arrow_down)
        self.tree.focus_set()

        info_frame = tk.Frame(main, bg="#1e1e1e", width=680)
        info_frame.pack(side="right", fill="both", expand=True, padx=(20, 0))
        info_frame.pack_propagate(False)

        self.img = tk.Label(info_frame, bg="#1e1e1e", text="Select a game", font=("", 13, "bold"))
        self.img.pack(pady=(30, 15), padx=20)

        self.title_canvas = tk.Canvas(info_frame, bg="#1e1e1e", height=50, highlightthickness=0)
        self.title_canvas.pack(pady=(0, 10), fill="x", padx=20)
        self.title_text_id = self.title_canvas.create_text(
            0, 25, text="", anchor="w", font=("", 16, "bold"), fill="#ffffff")

        right_grid = tk.Frame(info_frame, bg="#1e1e1e")
        right_grid.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        right_grid.grid_rowconfigure(0, weight=1)
        right_grid.grid_rowconfigure(1, weight=1)
        right_grid.grid_rowconfigure(2, weight=0)
        right_grid.grid_columnconfigure(0, weight=1)

        info_container = tk.LabelFrame(
            right_grid, text=" Game Info ", bg="#1e1e1e", fg="#ffffff",
            font=("", 11, "bold"), padx=14, pady=12, bd=1, relief="solid")
        info_container.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        self.details_text = tk.Text(
            info_container,
            bg=self.TEXT_BG,
            fg="#d0d0d0",
            font=("", 10),
            wrap="word",
            height=12,
            bd=0,
            highlightthickness=0,
            insertbackground="#60a0ff",
            spacing1=6, spacing2=4, spacing3=6,
            state="disabled"
        )
        self.details_text.pack(fill="both", expand=True, padx=5, pady=5)

        details_scroll = ttk.Scrollbar(info_container, orient="vertical", command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        details_scroll.pack(side="right", fill="y")

        desc_container = tk.LabelFrame(
            right_grid, text=" Description ", bg="#1e1e1e", fg="#ffffff",
            font=("", 11, "bold"), padx=14, pady=12, bd=1, relief="solid")
        desc_container.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        self.desc = tk.Text(
            desc_container,
            bg=self.TEXT_BG,
            fg="#d0d0d0",
            font=("", 10),
            wrap="word",
            height=12,
            bd=0,
            highlightthickness=0,
            insertbackground="#60a0ff",
            spacing1=6, spacing2=4, spacing3=6,
            state="disabled"
        )
        self.desc.pack(fill="both", expand=True, padx=5, pady=5)

        desc_scroll = ttk.Scrollbar(desc_container, orient="vertical", command=self.desc.yview)
        self.desc.configure(yscrollcommand=desc_scroll.set)
        desc_scroll.pack(side="right", fill="y")

        settings_container = tk.LabelFrame(
            right_grid, text=" Game Settings ", bg="#1e1e1e", fg="#ffffff",
            font=("", 11, "bold"), padx=16, pady=14, bd=1, relief="solid")
        settings_container.grid(row=2, column=0, sticky="nsew", pady=(6, 0))

        tk.Checkbutton(settings_container,
                       text="Playtime Overlay\n(Toggle on/off for anti-cheat safety)",
                       variable=self.overlay_var,
                       command=self.save_overlay_toggle,
                       bg="#1e1e1e", fg="#e0e0e0",
                       selectcolor="#2a2a2a",
                       activebackground="#1e1e1e",
                       activeforeground="#ffffff",
                       justify="left",
                       anchor="w").pack(anchor="w", pady=6, padx=(8, 8), fill="x")

        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=16, anchor="w", padx=28)

        self.add_var = tk.StringVar(value="Add Game")
        add_options = ["Pirated Games", "Steam Games", "Xbox Games"]
        add_dropdown = tk.OptionMenu(btn_frame, self.add_var, *add_options, command=self.handle_add_dropdown)
        add_dropdown.config(width=14, bg="#333", fg="#fff", relief="raised", font=("", 10))
        add_dropdown.pack(side="left", padx=(0, 10))

        tk.Button(btn_frame, text="Launch", width=12, command=self.launch, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Favorite ★", width=12, command=self.toggle_favorite, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Remove", width=12, command=self.remove, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Refresh All", width=12, command=self.refresh_all, bg="#333", fg="#fff").pack(side="left", padx=4)

        self.root.bind("<Return>", lambda e: self.launch())
        self.root.bind("<Delete>", lambda e: self.remove())
        self.root.bind("<Control-f>", lambda e: search_entry.focus_set())
        self.root.bind("<Control-a>", lambda e: self.handle_add_dropdown(self.add_var.get()))

        self.menu()
        self.apply_filters()

        if self.games:
            def _final_force_load():
                children = self.tree.get_children()
                if children:
                    first = children[0]
                    self.tree.selection_set(first)
                    self.tree.focus(first)
                    self.select(None)
                else:
                    self.root.after(400, _final_force_load)
            self.root.after(400, _final_force_load)

        self.root.after(100, self.process_queue)
        threading.Thread(target=self.global_playtime_tracker, daemon=True).start()

    def set_platform(self, plat):
        self.platform_filter.set(plat)
        for p, btn in self.platform_buttons.items():
            if p == plat:
                btn.config(bg="#505050", fg="#ffffff", relief="raised")
            else:
                btn.config(bg="#1e1e1e", fg="#dddddd", relief="flat")
        self.apply_filters()

    def _on_arrow_up(self, event):
        sel = self.tree.selection()
        if sel:
            prev = self.tree.prev(sel[0])
            if prev:
                self.tree.selection_set(prev)
                self.tree.focus(prev)
                self.select(None)
        return "break"

    def _on_arrow_down(self, event):
        sel = self.tree.selection()
        if sel:
            next_item = self.tree.next(sel[0])
            if next_item:
                self.tree.selection_set(next_item)
                self.tree.focus(next_item)
                self.select(None)
        return "break"

    def apply_filters(self):
        selected_iid = self.tree.selection()
        old_iid = selected_iid[0] if selected_iid else None

        search = self.search_var.get().lower()
        platform = self.platform_filter.get()
        sort_mode = self.sort_var.get()

        filtered_games = self.games.copy()
        if search:
            filtered_games = [g for g in filtered_games if search in g["name"].lower()]
        if platform != "All":
            filtered_games = [g for g in filtered_games if self.get_platform(g["path"]) == platform]

        reverse = False
        if sort_mode == "Name":
            key = lambda x: x["name"].lower()
        elif sort_mode == "Recently Played":
            key = lambda x: x.get("last_launch") or "0000-00-00 00:00:00"
            reverse = True
        elif sort_mode == "Playtime":
            key = lambda x: x.get("playtime", 0)
            reverse = True
        elif sort_mode == "Favorites":
            key = lambda x: (0 if x.get("favorite", False) else 1, x["name"].lower())
        else:
            key = lambda x: x["name"].lower()

        filtered_games.sort(key=key, reverse=reverse)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for g in filtered_games:
            playtime_str = self.format_playtime(g.get("playtime", 0))
            fav_text = "★" if g.get("favorite", False) else ""
            last = g.get("last_launch")
            recent_text = "-"
            if self.recent_format == "date_time":
                if last and isinstance(last, str):
                    try:
                        dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%m/%d/%Y")
                        hour = dt.hour % 12 or 12
                        minute = dt.strftime("%M")
                        ampm = dt.strftime("%p").lower()
                        time_str = f"{hour}:{minute} {ampm}"
                        recent_text = f"{date_str}\n{time_str.center(12)}"
                    except:
                        recent_text = "-"
            else:
                if last and isinstance(last, str):
                    try:
                        dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                        recent_text = self.time_ago(dt)
                    except:
                        recent_text = "-"

            orig_idx = self.games.index(g)
            iid = str(orig_idx)
            self.tree.insert("", "end", iid=iid, values=(
                g["name"],
                self.get_platform(g["path"]),
                playtime_str,
                fav_text,
                recent_text
            ))

        self.status.config(text=f"User: @{self.user} | Profile: {self.current} | {len(self.games)} game(s) | Showing: {len(filtered_games)}")

        if old_iid and old_iid in self.tree.get_children():
            self.tree.selection_set(old_iid)
            self.tree.focus(old_iid)
            self.tree.see(old_iid)
            self.select(None)

        if not self.tree.selection() and self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.see(first)
            self.select(None)

    def time_ago(self, dt):
        if dt is None:
            return "-"
        now = datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} min{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            return dt.strftime("%m/%d/%Y")

    def sort_by_column(self, col):
        mapping = {
            "name": "Name",
            "platform": "Platform",
            "playtime": "Playtime",
            "favorite": "Favorites",
            "recent": "Recently Played"
        }
        self.sort_var.set(mapping.get(col, "Name"))
        self.apply_filters()

    @staticmethod
    def format_playtime(seconds):
        if not seconds or seconds == 0:
            return "-"
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m"
        else:
            return f"{s}s"

    def format_duration(self, seconds):
        secs = int(seconds)
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"

    def get_platform(self, path):
        path_lower = path.lower()
        if "steam" in path_lower and "steamapps" in path_lower:
            return "Steam"
        elif "xboxgames" in path_lower:
            return "Xbox"
        return "Pirated"

    def show_context_menu(self, event):
        self.tree.selection_set(self.tree.identify_row(event.y))
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def toggle_favorite(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        game = self.games[idx]
        game["favorite"] = not game.get("favorite", False)
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
        self.apply_filters()

    def toggle_overlay(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        game = self.games[idx]
        game["overlay_enabled"] = not game.get("overlay_enabled", True)
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
        if idx == self.current_game_idx:
            self.overlay_var.set(game["overlay_enabled"])

    def save_overlay_toggle(self):
        if self.current_game_idx is None:
            return
        self.games[self.current_game_idx]["overlay_enabled"] = self.overlay_var.get()
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

    def refresh_selected_info(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        name = self.games[idx]["name"]
        threading.Thread(target=self.scrape_and_cache, args=(name, True), daemon=True).start()

    def refresh_all(self):
        for g in self.games:
            name = g["name"]
            if name not in self.pending_scrapes:
                self.pending_scrapes.add(name)
                threading.Thread(target=self.scrape_and_cache, args=(name, True), daemon=True).start()

    def scrape_and_cache(self, name, force=False):
        cache_file = os.path.join(IMG, f"{name.replace(' ', '_')}_info.json")
        if os.path.exists(cache_file) and not force:
            loaded = self.load(cache_file)
            if isinstance(loaded, dict):
                loaded.setdefault("image", PLACE)
                loaded.setdefault("title", name)
                loaded.setdefault("details", "")
                loaded.setdefault("description", "No description available")
                loaded.setdefault("appid", None)
                self.cache[name] = loaded
                return

        info = self.scrape(name)
        self.save(cache_file, info)
        self.cache[name] = info
        self.update_queue.put(self.apply_filters)

        selected = self.tree.selection()
        if selected:
            try:
                sel_idx = int(selected[0])
                if sel_idx < len(self.games) and self.games[sel_idx]["name"] == name:
                    self.update_queue.put(lambda: self.select(None))
            except:
                pass

    def scrape(self, name):
        img_path = os.path.join(IMG, f"{name.replace(' ', '_')}.jpg")
        try:
            search_url = f"https://steamcommunity.com/actions/SearchApps/{quote(name)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(search_url, headers=headers, timeout=12)
            if r.status_code == 200:
                apps = r.json()
                if apps:
                    app = next((a for a in apps if a["name"].lower() == name.lower()), apps[0])
                    appid = app["appid"]
                    details_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
                    resp = requests.get(details_url, headers=headers, timeout=12)
                    if resp.status_code == 200:
                        data = resp.json().get(str(appid), {}).get("data", {})
                        if data:
                            title = data.get("name", name)
                            release = data.get("release_date", {}).get("date", "Unknown")
                            developers = ", ".join(data.get("developers", ["Unknown"]))
                            genres = ", ".join([g["description"] for g in data.get("genres", [])])
                            short_desc = data.get("short_description", "No description available.")
                            details_lines = []
                            if developers and developers != "Unknown":
                                details_lines.append(f"Developer: {developers}")
                            if genres:
                                details_lines.append(f"Genres: {genres}")
                            if release:
                                details_lines.append(f"Release Date: {release}")
                            header_img = data.get("header_image")
                            if header_img and not os.path.exists(img_path):
                                try:
                                    img_data = requests.get(header_img, timeout=12).content
                                    img = Image.open(BytesIO(img_data))
                                    img.thumbnail((460, 620))
                                    img.save(img_path)
                                except Exception as e:
                                    print(f"Image save failed for {name}: {e}")
                            return {
                                "image": img_path if os.path.exists(img_path) else PLACE,
                                "title": title,
                                "details": "\n".join(details_lines),
                                "description": short_desc,
                                "appid": appid
                            }
        except Exception as e:
            print(f"Scrape error for {name}: {e}")

        return {
            "image": PLACE,
            "title": name,
            "details": "",
            "description": "No info found. Try Refresh All.",
            "appid": None
        }

    def show(self, img_path, title, details, desc):
        try:
            img = Image.open(img_path)
            img.thumbnail((460, 620))
            photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Image load failed: {e}")
            photo = ImageTk.PhotoImage(Image.open(PLACE))

        self.img.config(image=photo, text="")
        self.img.image = photo

        self.title_canvas.itemconfig(self.title_text_id, text="")
        self.root.after(120, lambda: self.start_title_scroll(title))

        self.details_text.config(state="normal")
        self.details_text.delete("1.0", tk.END)
        if details and details.strip():
            self.details_text.insert("1.0", details.strip())
        else:
            self.details_text.insert("1.0", "No additional information available")
        self.details_text.config(state="disabled")

        self.desc.config(state="normal")
        self.desc.delete("1.0", tk.END)
        if desc and desc.strip():
            self.desc.insert("1.0", desc.strip())
        else:
            self.desc.insert("1.0", "No description available for this title.\nThis game might be newly added or information is missing.")
        self.desc.config(state="disabled")

    def select(self, event):
        sel = self.tree.selection()
        if not sel:
            self.show(PLACE, "No game selected", "", "")
            self.overlay_var.set(True)
            return

        try:
            idx = int(sel[0])
        except (ValueError, TypeError):
            return

        if idx >= len(self.games):
            return

        self.current_game_idx = idx
        game = self.games[idx]
        self.overlay_var.set(game.get("overlay_enabled", True))

        cache_info = self.cache.get(game["name"])
        if cache_info is None or not isinstance(cache_info, dict):
            cache_info = {
                "image": PLACE,
                "title": game["name"],
                "details": "",
                "description": "Loading... (refresh if needed)",
                "appid": None
            }
            if game["name"] not in self.pending_scrapes:
                self.pending_scrapes.add(game["name"])
                threading.Thread(target=self.scrape_and_cache, args=(game["name"], True), daemon=True).start()

        self.show(
            cache_info.get("image", PLACE),
            cache_info.get("title", game["name"]),
            cache_info.get("details", ""),
            cache_info.get("description", "Loading...")
        )

    def create_game_overlay(self, game_name, session_start, initial_playtime):
        game = next((g for g in self.games if g["name"] == game_name), None)
        if not game or not game.get("overlay_enabled", False):
            return

        if self.overlay_window and self.overlay_window.winfo_exists():
            self.overlay_window.destroy()

        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes('-topmost', True)
        self.overlay_window.attributes('-alpha', 0.35)
        self.overlay_window.attributes('-disabled', True)
        self.overlay_window.configure(bg='#000000')

        self.overlay_window.geometry("520x34+0+0")

        self.overlay_label = tk.Label(
            self.overlay_window,
            text="Starting session...",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#000000",
            anchor="w",
            padx=14,
            pady=8,
            justify="left"
        )
        self.overlay_label.pack(fill="both", expand=True)

        self.overlay_running = True
        threading.Thread(target=self.overlay_update_loop, args=(session_start, initial_playtime, game_name), daemon=True).start()

    def overlay_update_loop(self, session_start, initial_playtime, game_name):
        while self.overlay_running:
            now = datetime.now()
            session_delta = now - session_start
            session_sec = session_delta.total_seconds()
            session_str = self.format_duration(session_sec)
            current_total = initial_playtime + session_sec
            total_str = self.format_duration(current_total)

            started_str = ""
            if session_sec >= 60:
                hour = session_start.hour % 12 or 12
                minute = f"{session_start.minute:02d}"
                ampm = session_start.strftime('%p').lower()
                started_str = f"started {hour}:{minute} {ampm}"

            parts = [
                f"Playing: {game_name}",
                f"Session: {session_str}",
            ]
            if started_str:
                parts.append(started_str)
            parts.append(f"Time Played: {total_str}")

            final_text = " • ".join(parts)

            def update_overlay_ui():
                if not self.overlay_window or not self.overlay_window.winfo_exists():
                    return
                self.overlay_label.config(text=final_text)
                self.overlay_label.update_idletasks()
                req_width = self.overlay_label.winfo_reqwidth() + 60
                req_height = self.overlay_label.winfo_reqheight() + 16
                max_width = 1100
                new_width = min(req_width, max_width)
                screen_width = self.overlay_window.winfo_screenwidth()
                self.overlay_window.geometry(f"{new_width}x{req_height}+{screen_width - new_width}+0")

            self.root.after(0, update_overlay_ui)
            time.sleep(1)

    def destroy_game_overlay(self):
        self.overlay_running = False
        if self.overlay_window and self.overlay_window.winfo_exists():
            self.overlay_window.destroy()
            self.overlay_window = None
        self.active_overlay_game = None

    def launch(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        game = self.games[idx]
        platform = self.get_platform(game["path"])
        game_name = game["name"]
        p = None
        try:
            if platform == "Steam":
                appid = self.cache.get(game["name"], {}).get("appid")
                if appid:
                    webbrowser.open(f"steam://run/{appid}")
                else:
                    p = subprocess.Popen([game["path"]], cwd=os.path.dirname(game["path"]))
            else:
                p = subprocess.Popen([game["path"]], cwd=os.path.dirname(game["path"]))

            self.current_game_process = p
            now = datetime.now()
            game["last_launch"] = now.strftime("%Y-%m-%d %H:%M:%S")
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

            if self.show_toast:
                Toast(self.root, f"Launched: {game['name']}")

            def monitor():
                if p:
                    p.wait()
                self.current_game_process = None

            threading.Thread(target=monitor, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch {game['name']}\n{str(e)}")
            self.log(f"Launch failed: {game['name']} - {e}")

    def global_playtime_tracker(self):
        while True:
            updated = False
            running_paths = set()

            for proc in psutil.process_iter(['exe', 'cmdline']):
                try:
                    exe = proc.info['exe']
                    if exe:
                        running_paths.add(os.path.normpath(exe).lower())
                    cmd = ' '.join(proc.info['cmdline'] or []).lower()
                    if cmd:
                        for g in self.games:
                            target = os.path.normpath(g['path']).lower()
                            if target in cmd:
                                running_paths.add(target)
                except:
                    pass

            active_game = None
            active_duration = timedelta(0)

            for game in self.games:
                target_path = os.path.normpath(game['path']).lower()
                is_running = target_path in running_paths
                state = self.states[game['name']]

                if is_running:
                    if not state['running']:
                        state['start_time'] = datetime.now()
                        state['running'] = True
                        game['last_launch'] = state['start_time'].strftime("%Y-%m-%d %H:%M:%S")
                        updated = True
                        if game.get("overlay_enabled", False) and self.active_overlay_game is None:
                            self.active_overlay_game = game['name']
                            initial_playtime = game['playtime']
                            self.create_game_overlay(game['name'], state['start_time'], initial_playtime)

                    state['session_duration'] = datetime.now() - state['start_time']

                    if not active_game or state['start_time'] > (self.states.get(active_game, {}).get('start_time') or datetime.min):
                        active_game = game['name']
                        active_duration = state['session_duration']
                else:
                    if state['running']:
                        duration_sec = (datetime.now() - state['start_time']).total_seconds()
                        game['playtime'] += duration_sec
                        state['running'] = False
                        state['start_time'] = None
                        state['session_duration'] = timedelta(0)
                        updated = True
                        if self.show_toast and duration_sec > 0:
                            Toast(self.root, f"Playtime added for {game['name']}: +{self.format_playtime(duration_sec)}")
                        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
                        if self.active_overlay_game == game['name']:
                            self.destroy_game_overlay()

            if updated:
                self.update_queue.put(self.apply_filters)

            if active_game:
                text = f"Currently playing: {active_game} - {self.format_duration(active_duration.total_seconds())}"
                self.update_queue.put(lambda: self.session_status_label.config(text=text))
            else:
                self.update_queue.put(lambda: self.session_status_label.config(text=""))

            time.sleep(1)

    def add_from_dir(self, initial_dir):
        if not os.path.exists(initial_dir):
            messagebox.showwarning("Path Not Found", f"Default path not found:\n{initial_dir}\nSelect manually.")
            initial_dir = filedialog.askdirectory(title="Select game folder")
            if not initial_dir:
                return

        file_path = filedialog.askopenfilename(initialdir=initial_dir, title="Select game executable",
                                              filetypes=[("Executable", "*.exe")])
        if not file_path:
            return

        default_name = os.path.basename(os.path.dirname(file_path))
        name = simpledialog.askstring("Game Name", "Enter display name:", initialvalue=default_name)
        if not name or not name.strip():
            return
        name = name.strip()

        if any(g["path"].lower() == file_path.lower() for g in self.games):
            messagebox.showwarning("Duplicate", "This game is already in your library.")
            return

        new_game = {
            "name": name,
            "path": file_path,
            "playtime": 0.0,
            "last_launch": None,
            "favorite": False,
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "overlay_enabled": True,
            "steam_imported_seconds": 0
        }

        self.games.append(new_game)
        self.states[new_game['name']] = {"running": False, "start_time": None, "session_duration": timedelta(0)}
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

        self.cache[name] = {"image": PLACE, "title": name, "details": "", "description": "Loading...", "appid": None}
        threading.Thread(target=self.scrape_and_cache, args=(name,), daemon=True).start()

        self.apply_filters()
        if self.show_toast:
            Toast(self.root, f"Added game: {name}")

    def remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        game_name = self.games[idx]["name"]
        if messagebox.askyesno("Remove Game", f"Remove '{game_name}' from library?"):
            del self.games[idx]
            if game_name in self.states:
                del self.states[game_name]
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self.apply_filters()
            if self.show_toast:
                Toast(self.root, f"Removed: {game_name}")

    def handle_add_dropdown(self, selection):
        if selection == "Pirated Games":
            self.add_from_dir(PATHS["pirated"])
        elif selection == "Steam Games":
            self.add_from_dir(PATHS["steam"])
        elif selection == "Xbox Games":
            self.add_from_dir(PATHS["xbox"])
        self.add_var.set("Add Game")

    def login(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("400x380")
        self.root.config(bg="#1e1e1e")
        self.center_window()

        tk.Label(self.root, text="Pirate Launcher", font=("", 16, "bold"), bg="#1e1e1e", fg="#fff").pack(pady=15)
        tk.Label(self.root, text="Create Account", font=("", 11, "bold"), bg="#1e1e1e", fg="#fff").pack(anchor="w", padx=40, pady=(10,5))

        entry = tk.Entry(self.root, font=("", 11), width=30, bg="#2a2a2a", fg="#fff", insertbackground="#fff")
        entry.pack(pady=5, padx=40)
        entry.focus()

        def create_account():
            username = entry.get().strip()
            if not username or username.lower() in {"admin", "system", "guest"}:
                messagebox.showwarning("Error", "Invalid username")
                return
            self.save(os.path.join(DIR, f"user_{username}.json"), {"username": username})
            self.save(os.path.join(DIR, "user.json"), {"username": username})
            self.user = username
            self.load_ui()

        tk.Button(self.root, text="Create & Sign In", command=create_account, bg="#333", fg="#fff", font=("", 10, "bold")).pack(pady=8)
        entry.bind('<Return>', lambda e: create_account())

        tk.Label(self.root, text="Sign In", font=("", 11, "bold"), bg="#1e1e1e", fg="#fff").pack(anchor="w", padx=40, pady=(15,5))

        users = [f[5:-5] for f in os.listdir(DIR) if f.startswith("user_") and f.endswith(".json")]
        user_var = tk.StringVar(value=users[0] if users else "")
        combo = ttk.Combobox(self.root, textvariable=user_var, values=users, state="readonly", width=28)
        combo.pack(pady=5, padx=40)

        def sign_in():
            username = user_var.get()
            if not username:
                return
            self.save(os.path.join(DIR, "user.json"), {"username": username})
            self.user = username
            self.load_ui()

        tk.Button(self.root, text="Sign In", command=sign_in, bg="#333", fg="#fff", font=("", 10, "bold")).pack(pady=8)
        combo.bind('<Return>', lambda e: sign_in())

    def menu(self):
        menubar = tk.Menu(self.root, bg="#333", fg="#fff")
        settings_menu = tk.Menu(menubar, tearoff=0, bg="#333", fg="#fff")
        menubar.add_cascade(label="Settings", menu=settings_menu)

        data_menu = tk.Menu(settings_menu, tearoff=0, bg="#333", fg="#fff")
        settings_menu.add_cascade(label="Data & Sync", menu=data_menu)

        data_menu.add_command(label="Reset Playtime (Current Profile)", command=self.reset_playtime)
        data_menu.add_command(label="Import Steam Playtime...", command=self.show_steam_sync_dialog)
        data_menu.add_command(label="Clear Saved Steam Playtime Import", command=self.clear_steam_import_watermark)
        data_menu.add_separator()
        data_menu.add_command(label="Create New Profile", command=self.new_profile)
        data_menu.add_command(label="Switch Profile", command=self.switch_profile)
        data_menu.add_command(label="Delete Profile", command=self.del_profile)
        data_menu.add_separator()
        data_menu.add_command(label="Clear All Games (Current Profile)", command=self.clear_games)
        data_menu.add_command(label="Clear All Launcher Data", command=self.clear_all)

        settings_menu.add_separator()
        settings_menu.add_command(label="Sign Out", command=self.sign_out)

        format_menu = tk.Menu(settings_menu, tearoff=0, bg="#333", fg="#fff")
        settings_menu.add_cascade(label="Recently Played Format", menu=format_menu)
        format_menu.add_command(label="Date & Time",
                               command=lambda: self.set_recent_format("date_time"))
        format_menu.add_command(label="Time Ago",
                               command=lambda: self.set_recent_format("time_ago"))

        self.root.config(menu=menubar)

    def reset_playtime(self):
        if messagebox.askyesno("Reset Playtime", "Reset ALL playtime to 0 for the current profile?\nThis cannot be undone."):
            for game in self.games:
                game["playtime"] = 0.0
                game["steam_imported_seconds"] = 0
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self.apply_filters()
            Toast(self.root, "Playtime reset to 0 for all games in this profile", 4000)

    def clear_steam_import_watermark(self):
        if messagebox.askyesno("Clear Steam Import Data", "This will reset the saved Steam playtime reference for all games to 0.\nNext import will pull full current Steam playtime again.\nContinue?"):
            for game in self.games:
                game["steam_imported_seconds"] = 0
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self.games = self.load(os.path.join(DIR, f"{self.current}_games.json"), default=[])
            self._migrate_games()
            self.states = {
                g["name"]: {"running": False, "start_time": None, "session_duration": timedelta(0)}
                for g in self.games
            }
            self.apply_filters()
            Toast(self.root, "Steam import reference cleared — next sync will import full playtime", 6000)

    def show_steam_sync_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Import Steam Playtime")
        dialog.geometry("540x425")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1e1e1e")

        tk.Label(dialog, text="Steam Playtime Import", font=("", 15, "bold"), bg="#1e1e1e", fg="#ffffff").pack(pady=16)

        content = tk.Frame(dialog, bg="#1e1e1e")
        content.pack(padx=35, pady=10, fill="both", expand=True)

        tk.Label(content, text="Your SteamID64 (17 digits):", bg="#1e1e1e", fg="#e0e0e0", font=("", 11)).pack(anchor="w")
        steamid_entry = tk.Entry(content, width=42, font=("", 11), bg="#2a2a2a", fg="#ffffff", insertbackground="#80bfff")
        steamid_entry.insert(0, self.last_steamid64)
        steamid_entry.pack(pady=(4, 6), fill="x")

        id_help = tk.Label(content, text="Don't know your SteamID64? Click here to find it →", fg="#4da6ff", bg="#1e1e1e",
                           cursor="hand2", font=("", 10, "underline"))
        id_help.pack(anchor="w", pady=(0, 14))
        id_help.bind("<Button-1>", lambda e: webbrowser.open_new("https://steamid.io/"))

        tk.Label(content, text="Steam Web API Key:", bg="#1e1e1e", fg="#e0e0e0", font=("", 11)).pack(anchor="w")
        apikey_entry = tk.Entry(content, width=42, font=("", 11), bg="#2a2a2a", fg="#ffffff", insertbackground="#80bfff")
        apikey_entry.insert(0, self.last_steam_apikey)
        apikey_entry.pack(pady=(4, 6), fill="x")

        api_help = tk.Label(content, text="Get your free Steam Web API Key here →", fg="#4da6ff", bg="#1e1e1e",
                            cursor="hand2", font=("", 10, "underline"))
        api_help.pack(anchor="w")
        api_help.bind("<Button-1>", lambda e: webbrowser.open_new("https://steamcommunity.com/dev/apikey"))

        tk.Label(content, text="(You need to be logged in to Steam in your browser to register a key)",
                 bg="#1e1e1e", fg="#888888", font=("", 9)).pack(anchor="w", pady=(6, 0))

        status_var = tk.StringVar(value="")
        status_label = tk.Label(dialog, textvariable=status_var, bg="#1e1e1e", fg="#88ff88",
                                wraplength=480, justify="center", font=("", 10))
        status_label.pack(pady=20, padx=30, fill="x")

        def do_sync():
            steamid = steamid_entry.get().strip()
            apikey = apikey_entry.get().strip()
            if not steamid or not steamid.isdigit() or len(steamid) != 17:
                status_var.set("Please enter a valid 17-digit SteamID64")
                status_label.config(fg="#ff6666")
                return
            if not apikey:
                status_var.set("Please enter your Steam Web API Key")
                status_label.config(fg="#ff6666")
                return

            self.last_steamid64 = steamid
            self.last_steam_apikey = apikey
            settings_path = os.path.join(DIR, "settings.json")
            settings = self.load(settings_path, default={})
            settings["last_steamid64"] = steamid
            settings["last_steam_apikey"] = apikey
            self.save(settings_path, settings)

            status_var.set("Connecting to Steam... please wait")
            status_label.config(fg="#ffcc44")
            dialog.update_idletasks()

            result = self.sync_steam_playtime(steamid, apikey)
            status_var.set(result)
            if "Success" in result:
                status_label.config(fg="#55ff55")
                dialog.after(2800, dialog.destroy)
            elif "No matching" in result or "No games" in result:
                status_label.config(fg="#ffcc44")
            else:
                status_label.config(fg="#ff6666")

        tk.Button(dialog, text="Import / Sync Playtime", command=do_sync,
                  bg="#4a6a8a", fg="#ffffff", activebackground="#5a7a9a",
                  font=("", 11, "bold"), width=26).pack(pady=12)

        tk.Button(dialog, text="Force Full Import", command=lambda: self.sync_steam_playtime(
            steamid_entry.get().strip(), apikey_entry.get().strip(), force_full=True),
                  bg="#6a4a8a", fg="#ffffff", activebackground="#7a5a9a",
                  font=("", 11, "bold"), width=26).pack(pady=6)

        tk.Button(dialog, text="Cancel", command=dialog.destroy,
                  bg="#333333", fg="#cccccc", font=("", 10)).pack(pady=4)

    def sync_steam_playtime(self, steamid, api_key, force_full=False):
        url = (
            f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
            f"?key={api_key}&steamid={steamid}&format=json&include_appinfo=1"
        )
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                return f"Steam API error (HTTP {r.status_code}) — check your key or internet"

            data = r.json()
            if "response" not in data or "games" not in data["response"]:
                msg = data.get("response", {}).get("message", "Unknown error")
                if "profile" in msg.lower() and "private" in msg.lower():
                    return "Steam profile must be public to see game details"
                return f"Steam returned: {msg}"

            games_from_steam = data["response"]["games"]
            if not games_from_steam:
                return "No games found in Steam library"

            updated = 0
            for api_game in games_from_steam:
                api_name = api_game.get("name", "").strip()
                api_seconds = api_game.get("playtime_forever", 0) * 60
                if api_seconds <= 0 or not api_name:
                    continue
                api_name_lower = api_name.lower()
                matched = False
                for game in self.games:
                    launcher_name_lower = game["name"].lower()
                    if launcher_name_lower == api_name_lower:
                        matched = True
                    elif "counter-strike" in launcher_name_lower and "counter-strike" in api_name_lower:
                        matched = True
                    elif "cs2" in launcher_name_lower or "cs:go" in launcher_name_lower:
                        if "counter-strike 2" in api_name_lower or "cs2" in api_name_lower:
                            matched = True
                    if matched:
                        prev_imported_sec = game.get("steam_imported_seconds", 0)
                        if force_full:
                            game["playtime"] = round(api_seconds, 2)
                            updated += 1
                        else:
                            new_steam_time = max(0, api_seconds - prev_imported_sec)
                            if new_steam_time > 0:
                                game["playtime"] = round(game.get("playtime", 0) + new_steam_time, 2)
                                updated += 1
                        game["steam_imported_seconds"] = api_seconds
                        break

            if updated > 0:
                self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
                self.games = self.load(os.path.join(DIR, f"{self.current}_games.json"), default=[])
                self._migrate_games()
                self.states = {
                    g["name"]: {"running": False, "start_time": None, "session_duration": timedelta(0)}
                    for g in self.games
                }
                self.apply_filters()
                return f"Success! Updated playtime for {updated} game(s) — total now includes Steam time"
            else:
                return "No updates — either no matching games or no new playtime detected on Steam"

        except requests.RequestException as e:
            return f"Network / API error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def set_recent_format(self, fmt):
        self.recent_format = fmt
        settings_path = os.path.join(DIR, "settings.json")
        settings = self.load(settings_path, default={
            "profile": "Default",
            "auto_refresh": True,
            "show_toast": True,
            "enable_logging": False,
            "recently_played_format": "date_time",
            "last_steamid64": "",
            "last_steam_apikey": ""
        })
        settings["recently_played_format"] = fmt
        self.save(settings_path, settings)
        self.apply_filters()
        Toast(self.root, f"Recently Played format set to: {'Date & Time' if fmt == 'date_time' else 'Time Ago'}", 2500)

    def sign_out(self):
        if os.path.exists(os.path.join(DIR, "user.json")):
            os.remove(os.path.join(DIR, "user.json"))
        self.login()

    def new_profile(self):
        name = simpledialog.askstring("New Profile", "Profile name:")
        if name and name.strip() and name.strip() not in self.profiles:
            self.profiles.append(name.strip())
            self.save(os.path.join(DIR, "profiles.json"), self.profiles)
            self.switch_profile(name.strip())

    def switch_profile(self, name=None):
        if not name:
            name = simpledialog.askstring("Switch Profile", "Enter profile name:\n" + "\n".join(self.profiles))
        if name and name in self.profiles and name != self.current:
            self.current = name
            settings_path = os.path.join(DIR, "settings.json")
            settings = self.load(settings_path, default={
                "profile": "Default",
                "auto_refresh": True,
                "show_toast": True,
                "enable_logging": False,
                "recently_played_format": "date_time",
                "last_steamid64": "",
                "last_steam_apikey": ""
            })
            settings["profile"] = self.current
            self.save(settings_path, settings)
            self.load_ui()

    def del_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("Cannot Delete", "Cannot delete the last profile.")
            return
        name = simpledialog.askstring("Delete Profile", "Profile to delete:\n" + "\n".join([p for p in self.profiles if p != self.current]))
        if name and name in self.profiles and name != self.current:
            if messagebox.askyesno("Confirm", f"Delete profile '{name}' and its data?"):
                self.profiles.remove(name)
                file = f"{name}_games.json"
                path = os.path.join(DIR, file)
                if os.path.exists(path):
                    os.remove(path)
                self.save(os.path.join(DIR, "profiles.json"), self.profiles)
                messagebox.showinfo("Deleted", f"Profile '{name}' deleted.")

    def clear_games(self):
        if messagebox.askyesno("Clear Games", "Remove all games from current profile?\nPlaytime and other data will be lost."):
            self.games = []
            self.states = {}
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self.apply_filters()
            Toast(self.root, "All games cleared from this profile", 3500)

    def clear_all(self):
        if messagebox.askyesno("DANGER ZONE", "Delete ALL launcher data?\nThis removes all profiles, games, cache, settings — irreversible!"):
            for file in os.listdir(DIR):
                if file.endswith(".json"):
                    os.remove(os.path.join(DIR, file))
            self.profiles = ["Default"]
            self.current = "Default"
            self.save(os.path.join(DIR, "profiles.json"), self.profiles)
            self.save(os.path.join(DIR, "settings.json"), {"profile": "Default"})
            self.load_ui()
            Toast(self.root, "All data cleared — fresh start", 5000)

if __name__ == "__main__":
    root = tk.Tk()
    app = Launcher(root)
    root.mainloop()
