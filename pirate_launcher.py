# pirate_launcher.py
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import json, os, subprocess, sys, requests, threading
from PIL import Image, ImageTk
from io import BytesIO
from urllib.parse import quote

# CONFIG
DIR = "Pirate Launcher Components"
IMG = os.path.join(DIR, "images")
os.makedirs(IMG, exist_ok=True)

PLACE = os.path.join(IMG, "no.png")
STEAM_PLACE = os.path.join(IMG, "steam.png")
XBOX_PLACE = os.path.join(IMG, "xbox.png")
PIRATE_PLACE = os.path.join(IMG, "pirate.png")

# Create placeholder
if not os.path.exists(PLACE):
    Image.new('RGB', (340, 460), (50, 50, 50)).save(PLACE)

# Platform badges
def create_badge(color, path):
    if not os.path.exists(path):
        Image.new('RGB', (16, 16), color).save(path)

create_badge((30, 215, 96), STEAM_PLACE)
create_badge((13, 183, 0), XBOX_PLACE)
create_badge((220, 20, 60), PIRATE_PLACE)

# Script dir
SCRIPT_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)

# Default paths
PATHS = {
    "pirated": SCRIPT_DIR,
    "steam": r"C:\Program Files (x86)\Steam\steamapps\common",
    "xbox": r"C:\XboxGames"
}

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Pirate Launcher")
        self.root.geometry("1400x560")
        self.root.minsize(1400, 560)
        self.root.config(bg="#1e1e1e")

        # Load user AFTER defining self.load
        self.user = self.load("user.json", "username")
        if self.user:
            self.load_ui()
        else:
            self.login()

    def load_ui(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.center_window()

        self.profiles = self.load("profiles.json", default=["Default"])
        settings = self.load("settings.json", default={"profile": "Default", "theme": "dark"})
        self.current = settings["profile"]
        self.theme = settings["theme"]

        self.colors = {
            "dark": {"bg":"#1e1e1e","fg":"#fff","btn":"#333","list":"#2a2a2a","sel":"#505050","stat":"#121212","statfg":"#ccc"},
            "light": {"bg":"#f8f9fa","fg":"#212529","btn":"#e9ecef","list":"#fff","sel":"#007bff","stat":"#dee2e6","statfg":"#495057"}
        }[self.theme]

        # LOAD GAMES
        self.games = self.load(f"{self.current}_games.json", default=[])

        # BUILD CACHE
        self.cache = {}
        self.pending_scrapes = set()
        for g in self.games:
            name = g["name"]
            cache_file = os.path.join(IMG, f"{name.replace(' ', '_')}_info.json")
            if os.path.exists(cache_file):
                self.cache[name] = self.load(cache_file)
            else:
                self.cache[name] = {"image": PLACE, "description": "Loading..."}
                if name not in self.pending_scrapes:
                    self.pending_scrapes.add(name)
                    threading.Thread(target=self.scrape_and_cache, args=(name,), daemon=True).start()

        # UI
        self.status = tk.Label(self.root, text="Ready", anchor="w", bg=self.colors["stat"], fg=self.colors["statfg"], font=("",9))
        self.status.pack(side="bottom", fill="x")

        main = tk.Frame(self.root, bg=self.colors["bg"])
        main.pack(fill="both", expand=True, padx=28, pady=(20,10))

        # TREEVIEW
        list_frame = tk.Frame(main, bg=self.colors["bg"])
        list_frame.pack(side="left", fill="both", expand=True, padx=(0,18))

        columns = ("name", "platform")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree", selectmode="browse")
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("name", width=980, anchor="w", minwidth=750)
        self.tree.column("platform", width=130, anchor="center", minwidth=90)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=self.colors["list"], foreground=self.colors["fg"],
                        fieldbackground=self.colors["list"], rowheight=32, font=("",10))
        style.map("Treeview", background=[("selected", self.colors["sel"])])

        v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        # INFO PANEL
        info_frame = tk.Frame(main, bg=self.colors["bg"], width=380)
        info_frame.pack(side="right", fill="both", padx=(18,0))
        info_frame.pack_propagate(False)

        self.img = tk.Label(info_frame, bg=self.colors["bg"], text="Select game", font=("",10))
        self.img.pack(pady=20, fill="x")

        self.desc = tk.Text(info_frame, bg=self.colors["list"], fg=self.colors["fg"], font=("",10),
                            wrap="word", state="disabled", height=20)
        desc_scroll = ttk.Scrollbar(info_frame, orient="vertical", command=self.desc.yview)
        self.desc.configure(yscrollcommand=desc_scroll.set)
        self.desc.pack(side="left", fill="both", expand=True, padx=(0,8))
        desc_scroll.pack(side="right", fill="y")

        self.tree.bind('<<TreeviewSelect>>', self.select)

        # UPDATE + AUTO-SELECT FIRST
        self.update_list()
        if self.games:
            self.root.after(100, self.select_first_game)

        # BUTTONS
        btn_frame = tk.Frame(self.root, bg=self.colors["bg"])
        btn_frame.pack(pady=16, anchor="w", padx=28)

        self.add_var = tk.StringVar(value="Add Game")
        add_options = ["Add Game", "Pirated Games", "Steam Games", "Xbox Games"]
        add_dropdown = tk.OptionMenu(btn_frame, self.add_var, *add_options, command=self.handle_add_dropdown)
        add_dropdown.config(width=14, bg=self.colors["btn"], fg=self.colors["fg"], relief="raised", font=("",10))
        add_dropdown.pack(side="left", padx=(0,10))

        tk.Button(btn_frame, text="Launch", width=12, command=self.launch, bg=self.colors["btn"], fg=self.colors["fg"]).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Remove", width=12, command=self.remove, bg=self.colors["btn"], fg=self.colors["fg"]).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Refresh", width=12, command=self.update_list, bg=self.colors["btn"], fg=self.colors["fg"]).pack(side="left", padx=4)

        self.menu()

    def select_first_game(self):
        if not self.games:
            return
        first_name = self.games[0]["name"]
        first_iid = self.tree.get_children()[0]

        self.tree.selection_set(first_iid)
        self.tree.focus(first_iid)

        c = self.cache.get(first_name, {})
        self.show(c.get("image", PLACE), c.get("description", "No info"))

        if c.get("description", "").startswith("Loading"):
            self.root.after(500, self.select_first_game)

    def get_platform(self, path):
        path_lower = path.lower()
        if "steam" in path_lower and "steamapps" in path_lower:
            return "Steam"
        elif "xboxgames" in path_lower:
            return "Xbox"
        else:
            return "Pirated"

    def update_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.games.sort(key=lambda x: x["name"].lower())
        for g in self.games:
            name = g["name"]
            platform = self.get_platform(g["path"])
            self.tree.insert("", "end", values=(name, platform))
        self.status.config(text=f"User: @{self.user} | {self.current} | {len(self.games)} game(s)")

    def scrape_and_cache(self, name):
        info = self.scrape(name)
        cache_file = os.path.join(IMG, f"{name.replace(' ', '_')}_info.json")
        self.save(cache_file, info)
        self.cache[name] = info
        self.root.after(0, self.update_list)
        if self.tree.selection():
            sel_idx = self.tree.index(self.tree.selection()[0])
            if sel_idx < len(self.games) and self.games[sel_idx]["name"] == name:
                self.root.after(0, lambda: self.select(None))

    def handle_add_dropdown(self, selection):
        if selection == "Pirated Games":
            self.add_from_dir(PATHS["pirated"])
        elif selection == "Steam Games":
            self.add_from_dir(PATHS["steam"])
        elif selection == "Xbox Games":
            self.add_from_dir(PATHS["xbox"])
        self.add_var.set("Add Game")

    def add_from_dir(self, initial_dir):
        if not os.path.exists(initial_dir):
            messagebox.showwarning("Not Found", f"Path not found:\n{initial_dir}")
            return
        p = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("EXE","*.exe")])
        if not p: return
        n = simpledialog.askstring("Name", "Game name:", initialvalue=os.path.basename(os.path.dirname(p)))
        if not n or not n.strip(): return
        n = n.strip()
        if any(g.get("path","").lower()==p.lower() for g in self.games):
            messagebox.showwarning("","Already added")
            return

        self.games.append({"name": n, "path": p})
        self.save(f"{self.current}_games.json", self.games)
        self.update_list()

        self.cache[n] = {"image": PLACE, "description": "Loading..."}
        threading.Thread(target=self.scrape_and_cache, args=(n,), daemon=True).start()

        messagebox.showinfo("Added", f"'{n}' added!")

    def center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def login(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("400x380")
        self.root.config(bg="#1e1e1e")
        self.center_window()

        tk.Label(self.root, text="Pirate Launcher", font=("",16,"bold"), bg="#1e1e1e", fg="#fff").pack(pady=15)
        tk.Label(self.root, text="Create Account", font=("",11,"bold"), bg="#1e1e1e", fg="#fff").pack(anchor="w", padx=40, pady=(10,5))
        e = tk.Entry(self.root, font=("",11), width=30, bg="#2a2a2a", fg="#fff", insertbackground="#fff")
        e.pack(pady=5, padx=40)
        e.focus()

        def make():
            n = e.get().strip()
            if not n or n.lower() in {"admin","system","guest"}:
                messagebox.showwarning("Error", "Invalid name")
                return
            self.save(f"user_{n}.json", {"username": n})
            self.save("user.json", {"username": n})
            self.user = n
            self.load_ui()

        tk.Button(self.root, text="Create & Sign In", command=make, bg="#333", fg="#fff", font=("",10,"bold")).pack(pady=8)
        e.bind('<Return>', lambda _: make())

        tk.Label(self.root, text="Sign In", font=("",11,"bold"), bg="#1e1e1e", fg="#fff").pack(anchor="w", padx=40, pady=(15,5))
        users = [f[5:-5] for f in os.listdir(DIR) if f.startswith("user_") and f.endswith(".json")]
        var = tk.StringVar(value=users[0] if users else "")
        drop = ttk.Combobox(self.root, textvariable=var, values=users, state="readonly", width=28)
        drop.pack(pady=5, padx=40)

        def signin():
            n = var.get()
            if not n: return
            self.save("user.json", {"username": n})
            self.user = n
            self.load_ui()

        tk.Button(self.root, text="Sign In", command=signin, bg="#333", fg="#fff", font=("",10,"bold")).pack(pady=8)
        drop.bind('<Return>', lambda _: signin())

    def menu(self):
        m = tk.Menu(self.root, bg=self.colors["bg"], fg=self.colors["fg"])
        s = tk.Menu(m, tearoff=0, bg=self.colors["bg"], fg=self.colors["fg"])
        m.add_cascade(label="Settings", menu=s)
        s.add_command(label="Toggle Theme", command=self.toggle_theme)
        s.add_command(label="Sign Out", command=lambda: [os.remove("user.json") if os.path.exists("user.json") else None, self.login()])
        p = tk.Menu(s, tearoff=0, bg=self.colors["bg"], fg=self.colors["fg"])
        s.add_cascade(label="Profiles", menu=p)
        p.add_command(label="Create", command=self.new_profile)
        p.add_command(label="Switch", command=self.switch_profile)
        p.add_command(label="Delete", command=self.del_profile)
        s.add_separator()
        s.add_command(label="Clear Games", command=self.clear_games)
        s.add_command(label="Clear All", command=self.clear_all)
        self.root.config(menu=m)

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.save("settings.json", {"theme": self.theme, "profile": self.current})
        self.load_ui()

    def new_profile(self):
        n = simpledialog.askstring("New Profile", "Name:")
        if n and n.strip() and n.strip() not in self.profiles:
            self.profiles.append(n.strip())
            self.save("profiles.json", self.profiles)
            self.switch_profile(n.strip())

    def switch_profile(self, name=None):
        if not name:
            name = simpledialog.askstring("Switch", "\n".join(self.profiles))
        if name and name in self.profiles and name != self.current:
            self.current = name
            self.save("settings.json", {"theme": self.theme, "profile": self.current})
            self.load_ui()

    def del_profile(self):
        if len(self.profiles) <= 1: return
        p = simpledialog.askstring("Delete", "\n".join([x for x in self.profiles if x != self.current]))
        if p and p in self.profiles and p != self.current:
            if messagebox.askyesno("Confirm", f"Delete '{p}'?"):
                self.profiles.remove(p)
                f = f"{p}_games.json"
                if os.path.exists(f): os.remove(f)
                self.save("profiles.json", self.profiles)
                messagebox.showinfo("Done", f"'{p}' deleted")

    def clear_games(self):
        if messagebox.askyesno("Clear", "Remove all games?"):
            self.games = []
            self.save(f"{self.current}_games.json", self.games)
            self.update_list()

    def clear_all(self):
        if messagebox.askyesno("WARNING", "Delete ALL data?"):
            for f in os.listdir(DIR):
                if f.endswith(".json"):
                    os.remove(os.path.join(DIR, f))
            self.profiles = ["Default"]
            self.switch_profile("Default")

    def select(self, e):
        sel = self.tree.selection()
        if not sel:
            self.show(PLACE, "No game selected")
            return
        idx = self.tree.index(sel[0])
        if idx >= len(self.games):
            return
        n = self.games[idx]["name"]
        c = self.cache.get(n, {})
        self.show(c.get("image", PLACE), c.get("description", "No info"))

    def show(self, img_path, desc):
        try:
            i = Image.open(img_path)
            i.thumbnail((340, 460))
            p = ImageTk.PhotoImage(i)
        except:
            i = Image.open(PLACE)
            p = ImageTk.PhotoImage(i)
        self.img.config(image=p, text="")
        self.img.image = p
        self.desc.config(state="normal")
        self.desc.delete(1.0, "end")
        self.desc.insert(1.0, desc)
        self.desc.config(state="disabled")

    def scrape(self, name):
        try:
            r = requests.get(f"https://api.rawg.io/api/games?search={name.replace(' ', '%20')}&page_size=5", timeout=10)
            if r.status_code == 200 and r.json().get("results"):
                results = r.json()["results"]
                exact = next((g for g in results if g["name"].lower() == name.lower()), None)
                g = exact or results[0]
                desc = f"{g['name']} - {', '.join([x['name'] for x in g.get('genres',[])])}\n\n{g.get('description','')[:300]}..."
                img_path = os.path.join(IMG, f"{name.replace(' ', '_')}.jpg")
                if g.get("background_image") and not os.path.exists(img_path):
                    i = requests.get(g["background_image"], timeout=10)
                    if i.status_code == 200:
                        Image.open(BytesIO(i.content)).thumbnail((340,460)).save(img_path)
                return {"image": img_path if os.path.exists(img_path) else PLACE, "description": desc}
        except: pass

        try:
            search_url = f"https://steamcommunity.com/actions/SearchApps/{quote(name)}"
            r = requests.get(search_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                apps = r.json()
                if apps:
                    exact_match = next((app for app in apps if app["name"].lower() == name.lower()), None)
                    app = exact_match or apps[0]
                    app_id = str(app["appid"])
                    api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
                    resp = requests.get(api_url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json().get(app_id, {}).get("data", {})
                        if data:
                            title = data.get("name", name)
                            short_desc = data.get("short_description", "No description.")
                            header_img = data.get("header_image")
                            img_path = os.path.join(IMG, f"{name.replace(' ', '_')}_cover.jpg")
                            if header_img and not os.path.exists(img_path):
                                img_resp = requests.get(header_img, timeout=10)
                                if img_resp.status_code == 200:
                                    img = Image.open(BytesIO(img_resp.content))
                                    img.thumbnail((340, 460), Image.Resampling.LANCZOS)
                                    img.save(img_path)
                            return {
                                "image": img_path if os.path.exists(img_path) else STEAM_PLACE,
                                "description": f"{title}\n\n{short_desc}"
                            }
        except Exception as e:
            print(f"Steam API error: {e}")

        return {"image": PLACE, "description": "No info found."}

    def launch(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        if idx >= len(self.games): return
        g = self.games[idx]
        try:
            subprocess.Popen([g["path"]], cwd=os.path.dirname(g["path"]))
        except:
            messagebox.showerror("", "Failed to launch")

    def remove(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        if idx >= len(self.games): return
        if messagebox.askyesno("", "Remove?"):
            del self.games[idx]
            self.save(f"{self.current}_games.json", self.games)
            self.update_list()

    def load(self, f, key=None, default=None):
        p = os.path.join(DIR, f)
        if not os.path.exists(p): return default
        try:
            with open(p, encoding="utf-8") as file:
                d = json.load(file)
            return d.get(key) if key else d
        except:
            return default

    def save(self, f, d):
        try:
            with open(os.path.join(DIR, f), "w", encoding="utf-8") as file:
                json.dump(d, file, indent=4)
        except:
            pass

if __name__ == "__main__":
    try:
        root = tk.Tk()
        Launcher(root)
        root.mainloop()
    except Exception as e:
        tk.Tk().withdraw()
        messagebox.showerror("Crash", str(e))