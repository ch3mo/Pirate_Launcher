import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk
import hashlib
import json
import os
import subprocess
import sys
import requests
import threading
from PIL import Image, ImageOps, ImageTk
from io import BytesIO
from urllib.parse import quote
from datetime import datetime, timedelta
import queue
import logging
import psutil
import time
import webbrowser
import asyncio
import aiohttp
import re
import difflib
import unicodedata
from pathlib import Path
import pyperclip
from tqdm import tqdm
from urllib.parse import urlparse

DIR_NAME = "Pirate Launcher Components"
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
DIR = os.path.join(BASE_DIR, DIR_NAME)
IMG = os.path.join(DIR, "images")
os.makedirs(DIR, exist_ok=True)
os.makedirs(IMG, exist_ok=True)

PLACE = os.path.join(IMG, "no.png")
STAR_PLACE = os.path.join(IMG, "star.png")
STAR_EMPTY = os.path.join(IMG, "star_empty.png")

ICON_URLS = {
    "steam": "https://i.ibb.co/XkYLYpCC/steam-icon.png",
    "xbox": "https://i.ibb.co/23dV3x7n/xbox-icon.png",
    "pirate": "https://i.ibb.co/Zp3fwj5q/pirate-icon.png",
}

def download_icon_if_missing(name, url):
    path = os.path.join(IMG, f"{name}_icon_24.png")
    if not os.path.exists(path):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
        except:
            pass
    return path

def safe_create_image(size, color, path, mode='RGB'):
    if os.path.exists(path):
        return
    try:
        img = Image.new(mode, size, color)
        img.save(path)
    except:
        pass

safe_create_image((480, 640), (50, 50, 50), PLACE)
safe_create_image((20, 20), (255, 215, 0), STAR_PLACE)
safe_create_image((20, 20), (0, 0, 0, 0), STAR_EMPTY, mode='RGBA')

PIRATED_GAMES_DIR = Path(BASE_DIR) / "Pirated Games"
PIRATED_GAMES_DIR.mkdir(parents=True, exist_ok=True)

PATHS = {
    "pirated": str(PIRATED_GAMES_DIR),
    "steam": r"C:\Program Files (x86)\Steam\steamapps\common",
    "xbox": r"C:\XboxGames"
}

def parse_geometry(geom_str):
    if not geom_str:
        return None
    try:
        parts = geom_str.replace('+', 'x').split('x')
        if len(parts) == 4:
            return tuple(map(int, parts))
        return None
    except:
        return None


# Backup downloads land in the same “Pirated Games” folder as the add-game default.
BACKUP_DOWNLOAD_FOLDER = PIRATED_GAMES_DIR

# Non-capturing path group so findall returns full URLs (not just the path fragment).
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+\.[a-zA-Z0-9]{2,}(?:/[^\s<>"\']*)?')

# Steam rejects bare scripts/bots without browser-like headers on many endpoints.
_STEAM_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
STEAM_COMMUNITY_HEADERS = {
    "User-Agent": _STEAM_UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://steamcommunity.com",
    "Referer": "https://steamcommunity.com/",
}
STEAM_STORE_HEADERS = {
    "User-Agent": _STEAM_UA,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://store.steampowered.com/",
}
STEAM_IMAGE_HEADERS = {
    "User-Agent": _STEAM_UA,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://store.steampowered.com/",
}

# Total launcher-tracked time across the profile (sum of per-game launcher_playtime_seconds).
PROFILE_ACHIEVEMENTS = [
    ("profile_pt_30m", 30 * 60, "First Mate", "30 minutes total time tracked by the launcher (not Steam import)."),
    ("profile_pt_2h", 2 * 3600, "Seasoned Sailor", "2 hours total launcher-tracked playtime."),
    ("profile_pt_10h", 10 * 3600, "Navigator", "10 hours total launcher-tracked playtime."),
    ("profile_pt_50h", 50 * 3600, "Captain", "50 hours total launcher-tracked playtime."),
    ("profile_pt_200h", 200 * 3600, "Legend of the Seas", "200 hours total launcher-tracked playtime."),
]
# Per-game ids are suffixed with __<path_key> (see _game_achievement_key).
GAME_ACHIEVEMENTS = [
    ("game_pt_15m", 15 * 60, "Anchored", "15 minutes launcher-tracked in this game."),
    ("game_pt_1h", 3600, "Deep Dive", "1 hour launcher-tracked in this game."),
    ("game_pt_25h", 25 * 3600, "Marathon", "25 hours launcher-tracked in this game."),
]

# Minimum launcher-tracked seconds before a title counts toward platform "games played" tallies.
SECRET_ACHIEVEMENT_MIN_SEC = 60

# Secret achievements: launcher-tracked only. Tuple =
# (id, kind, need, title, description, hint_theme_for_locked_ui)
# kind: pirate_count | steam_count | xbox_count | pirated_hours | steam_hours | xbox_hours | triple_platform
# need: threshold (counts or seconds); ignored for triple_platform.
SECRET_ACHIEVEMENTS = [
    ("secret_true_pirate", "pirate_count", 1, "True Pirate", "You played a Pirated game through the launcher — no Steam import, just sea legs.", "Pirated"),
    ("secret_high_seas", "pirate_count", 10, "Welcome to the High Seas", "Ten Pirated titles with real launcher time — the crew is assembling.", "Pirated"),
    ("secret_blackbeard", "pirate_count", 50, "Blackbeard", "Fifty Pirated games with tracked time — you're running a fleet.", "Pirated"),
    ("secret_parrot_squad", "pirate_count", 25, "Parrot Squad", "Twenty-five Pirated games — the birds won't stop squawking.", "Pirated"),
    ("secret_through_our_port", "steam_count", 1, "Through Our Port", "Oh, you like this launcher that much? First Steam game played through us.", "Steam"),
    ("secret_onlyfans", "steam_count", 10, "OnlyFans", "Ten Steam games launched from here — you're basically subscribed to the launcher.", "Steam"),
    ("secret_steam_armada", "steam_count", 25, "Steam Armada", "Twenty-five Steam titles with real launcher time — admiral energy.", "Steam"),
    ("secret_steam_proxy", "steam_hours", 50 * 3600, "Steamworks by Proxy", "50+ launcher-tracked hours on Steam installs — the store is optional.", "Steam"),
    ("secret_xbox_green", "xbox_count", 1, "Green on the Horizon", "First Xbox game tracked through the launcher — wrong green, still counts.", "Xbox"),
    ("secret_game_pass_moment", "xbox_hours", 20 * 3600, "Rent to Own", "20+ launcher-tracked hours on Xbox paths — possession is nine tenths.", "Xbox"),
    ("secret_buried_hours", "pirated_hours", 100 * 3600, "Buried Hours", "100+ launcher-tracked hours on Pirated paths — dig deeper.", "Pirated"),
    ("secret_tricorn", "triple_platform", 0, "Tricorn", "Steam, Xbox, and Pirated — at least one tracked game on each. Three corners, one hat.", "Mixed"),
    ("secret_plank_walk", "steam_count", 3, "Review Bomber", "Three Steam games through the launcher — you're leaving footprints on the deck.", "Steam"),
    ("secret_rum_runner", "pirate_count", 5, "Rum Runner", "Five Pirated games — small cargo, big attitude.", "Pirated"),
]

# Gamerscore per achievement (difficulty / grind). Game entries use suffix before __<path_key>.
GAMERSCORE_PROFILE_POINTS = {
    "profile_pt_30m": 5,
    "profile_pt_2h": 10,
    "profile_pt_10h": 15,
    "profile_pt_50h": 25,
    "profile_pt_200h": 50,
}
GAMERSCORE_GAME_SUFFIX_POINTS = {
    "game_pt_15m": 5,
    "game_pt_1h": 10,
    "game_pt_25h": 25,
}
GAMERSCORE_SECRET_POINTS = {
    "secret_true_pirate": 5,
    "secret_rum_runner": 10,
    "secret_high_seas": 20,
    "secret_parrot_squad": 25,
    "secret_blackbeard": 50,
    "secret_through_our_port": 5,
    "secret_plank_walk": 10,
    "secret_onlyfans": 20,
    "secret_steam_armada": 30,
    "secret_steam_proxy": 35,
    "secret_xbox_green": 5,
    "secret_game_pass_moment": 25,
    "secret_buried_hours": 40,
    "secret_tricorn": 30,
}

class Toast:
    def __init__(self, master, message, duration=3500, title=None, title_color="#ffd77a"):
        self.toast = tk.Toplevel(master)
        self.toast.wm_overrideredirect(True)
        self.toast.attributes('-topmost', True)
        self.toast.attributes('-alpha', 0.88)
        self.toast.config(bg="#0f0f0f")
        container = tk.Frame(self.toast, bg="#0f0f0f")
        container.pack(padx=14, pady=10)
        wrap = 480
        if title:
            tk.Label(
                container,
                text=title,
                bg="#0f0f0f",
                fg=title_color,
                font=("Segoe UI", 12, "bold"),
                justify="left",
                wraplength=wrap,
            ).pack(anchor="w")
            self.label = tk.Label(
                container,
                text=message,
                bg="#0f0f0f",
                fg="#e8e8e8",
                font=("Segoe UI", 10),
                justify="left",
                wraplength=wrap,
            )
            self.label.pack(anchor="w", pady=(6, 0))
        else:
            self.label = tk.Label(
                container,
                text=message,
                bg="#0f0f0f",
                fg="#eeeeee",
                font=("Segoe UI", 11),
                justify="left",
                wraplength=wrap,
            )
            self.label.pack()
        container.update_idletasks()
        req_width = container.winfo_reqwidth() + 48
        req_height = container.winfo_reqheight() + 32
        MAX_W = 580
        MAX_H = 320 if title else 220
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

class DownloadManagerWindow:
    """Fetch backup / archive links into the launcher directory tree (daemon asyncio thread)."""

    _HTTP_HEADERS = {
        "User-Agent": _STEAM_UA,
        "Accept": "*/*",
    }

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("Backup downloads")
        self.window.geometry("880x620")
        self.window.minsize(780, 520)
        self.window.configure(bg="#1e1e1e")
        self.running = True

        self.download_queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(4)
        self.active_tasks = []
        self.log_lines = []
        self.loop = None
        self._loop_ready = threading.Event()

        top_frame = tk.Frame(self.window, bg="#1e1e1e")
        top_frame.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(top_frame, text="Backup downloads", font=("", 15, "bold"), bg="#1e1e1e", fg="#ffffff").pack(side="left")

        tk.Button(top_frame, text="Clear Log", command=self.clear_log, bg="#444", fg="#eee", width=12).pack(side="right", padx=6)
        tk.Button(top_frame, text="Paste & Download", command=self.paste_and_queue, bg="#5a7a9a", fg="#ffffff", width=16).pack(side="right", padx=6)

        tk.Label(
            self.window,
            text=(
                "Use this for backup copies of games to install and play from your library. "
                "Files save to the Pirated Games folder next to this launcher (same place as Add Game → Pirated Games). "
                "Paste http(s) links, or copy a URL to the clipboard — links are picked up automatically."
            ),
            bg="#1e1e1e",
            fg="#999999",
            font=("", 10),
            wraplength=820,
            justify="left",
        ).pack(fill="x", padx=14, pady=(0, 10))

        mid = tk.Frame(self.window, bg="#1e1e1e")
        mid.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        self.log_text = tk.Text(mid, bg="#0f0f0f", fg="#d0d0d0", font=("", 10), wrap="word", state="disabled", height=18)
        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        bottom_frame = tk.Frame(self.window, bg="#1e1e1e")
        bottom_frame.pack(fill="x", padx=14, pady=10)

        tk.Label(bottom_frame, text="Pirated games folder:", bg="#1e1e1e", fg="#ccc").pack(side="left")
        self.folder_var = tk.StringVar(value=str(BACKUP_DOWNLOAD_FOLDER))
        tk.Entry(bottom_frame, textvariable=self.folder_var, width=48, bg="#2a2a2a", fg="#eee", insertbackground="#80d4ff").pack(side="left", padx=8, fill="x", expand=True)
        tk.Button(bottom_frame, text="Browse", command=self.browse_folder, bg="#444", fg="#eee", width=10).pack(side="left")

        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self._run_async_loop, daemon=True, name="DownloadManager-async").start()
        self.window.after(1200, self.check_clipboard_loop)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)

    def clear_log(self):
        self.log_lines = []
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def log(self, msg):
        """Thread-safe: marshals to the Tk main thread when called from async workers."""
        if threading.current_thread() is threading.main_thread():
            self._log_append(msg)
        else:
            self.window.after(0, lambda m=msg: self._log_append(m))

    def _log_append(self, msg):
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.log_lines.append(line)
        if len(self.log_lines) > 400:
            self.log_lines.pop(0)

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", "".join(self.log_lines))
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def paste_and_queue(self):
        if not self._loop_ready.is_set():
            self.window.after(100, self.paste_and_queue)
            return
        if not self.loop or not self.loop.is_running():
            self.log("Download engine is not running.")
            return
        try:
            text = pyperclip.paste().strip()
            if not text:
                return
            urls = URL_PATTERN.findall(text)
            added = 0
            for url in urls:
                if len(url) > 12 and url.lower().startswith(("http://", "https://")):
                    asyncio.run_coroutine_threadsafe(self.download_queue.put(url), self.loop)
                    added += 1
            if added > 0:
                self.log(f"Queued {added} link(s) from clipboard")
            else:
                self.log("No valid download links found in clipboard")
        except Exception:
            self.log("Clipboard access error")

    async def download_file(self, session, url):
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=120)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    self.log(f"[{resp.status}] {url}")
                    return

                disp = resp.headers.get("Content-Disposition")
                fname = None
                if disp and "filename=" in disp:
                    part = disp.split("filename=", 1)[1].strip().strip('"').split(";")[0]
                    if part:
                        fname = Path(part).name
                if not fname:
                    fname = Path(urlparse(url).path).name
                if not fname or fname in ("/", ""):
                    fname = f"download_{datetime.now():%Y%m%d_%H%M%S}"
                elif "." not in fname:
                    fname = f"{fname}_{datetime.now():%Y%m%d_%H%M%S}"

                save_dir = Path(self.folder_var.get())
                try:
                    save_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self.log(f"Cannot create folder {save_dir}: {e}")
                    return

                save_path = save_dir / fname

                if save_path.exists():
                    stem, ext = save_path.stem, save_path.suffix
                    i = 1
                    while (newpath := save_path.with_stem(f"{stem} ({i})")).exists():
                        i += 1
                    save_path = newpath

                total = int(resp.headers.get("content-length", 0) or 0)
                size_hint = f"{total / 1024 / 1024:.1f} MiB" if total > 0 else "size unknown"

                self.log(f"Starting: {save_path.name}  ({size_hint})")

                chunk_size = 256 * 1024

                with open(save_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        if chunk:
                            f.write(chunk)

                self.log(f"Completed → {save_path.name}")

        except Exception as e:
            self.log(f"Failed {url} → {type(e).__name__}: {e}")

    async def worker(self):
        async with aiohttp.ClientSession(headers=self._HTTP_HEADERS) as session:
            while self.running:
                try:
                    url = await asyncio.wait_for(self.download_queue.get(), timeout=6.0)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                try:
                    async with self.semaphore:
                        await self.download_file(session, url)
                except asyncio.CancelledError:
                    break
                finally:
                    try:
                        self.download_queue.task_done()
                    except ValueError:
                        pass

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        for _ in range(4):
            self.active_tasks.append(self.loop.create_task(self.worker()))
        self._loop_ready.set()
        self.loop.run_forever()

    def check_clipboard_loop(self):
        if not self.running:
            return
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
            return

        if not self._loop_ready.is_set() or not self.loop or not self.loop.is_running():
            self.window.after(1000, self.check_clipboard_loop)
            return

        try:
            text = pyperclip.paste() or ""
            urls = URL_PATTERN.findall(text)
            if urls:
                for url in urls:
                    if len(url) > 12 and url.lower().startswith(("http://", "https://")):
                        asyncio.run_coroutine_threadsafe(self.download_queue.put(url), self.loop)
                        self.log(f"Auto-detected → {url}")
                pyperclip.copy("")
        except Exception:
            pass

        self.window.after(1800, self.check_clipboard_loop)

    def on_close(self):
        self.running = False
        if self.loop and self.loop.is_running():

            def shutdown():
                for task in self.active_tasks:
                    task.cancel()
                self.loop.stop()

            self.loop.call_soon_threadsafe(shutdown)
        self.window.destroy()

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Pirate Launcher")
        self.profiles = self.load(os.path.join(DIR, "profiles.json"), default=["Default"])
        self.current = "Default"
        self.user = None
        self.games = []
        self.states = {}
        self.cache = {}
        self.pending_scrapes = set()
        self.update_queue = queue.Queue()
        self.current_game_process = None
        self.current_game_idx = None
        self._panel_resize_job = None
        self._last_cover_path = None
        self._cover_photo_ref = None
        self.achievements_win = None
        self.load_user()

    def get_settings_path(self, profile=None):
        if profile is None:
            profile = self.current
        return os.path.join(DIR, f"{profile}_settings.json")

    def get_achievements_path(self, profile=None):
        if profile is None:
            profile = self.current
        return os.path.join(DIR, f"{profile}_achievements.json")

    @staticmethod
    def _gamerscore_points_for_unlock_id(aid):
        if aid in GAMERSCORE_PROFILE_POINTS:
            return GAMERSCORE_PROFILE_POINTS[aid]
        if aid in GAMERSCORE_SECRET_POINTS:
            return GAMERSCORE_SECRET_POINTS[aid]
        if "__" in aid:
            try:
                left, _ = aid.rsplit("__", 1)
            except ValueError:
                return 0
            return GAMERSCORE_GAME_SUFFIX_POINTS.get(left, 0)
        return 0

    def _gamerscore_total(self):
        return sum(self._gamerscore_points_for_unlock_id(aid) for aid in self._load_achievements_unlocked())

    def update_gamerscore_label(self):
        if not hasattr(self, "gamerscore_var"):
            return
        try:
            total = self._gamerscore_total()
            self.gamerscore_var.set(f"{total:,} G")
        except (tk.TclError, AttributeError):
            pass

    def _load_achievements_unlocked(self):
        data = self.load(self.get_achievements_path(), default={})
        if not isinstance(data, dict):
            return set()
        u = data.get("unlocked")
        if isinstance(u, list):
            return set(str(x) for x in u)
        return set()

    def _save_achievements_unlocked(self, unlocked_set):
        self.save(self.get_achievements_path(), {"unlocked": sorted(unlocked_set)})

    @staticmethod
    def _game_achievement_key(game):
        p = os.path.normpath((game or {}).get("path") or "").lower().encode("utf-8", errors="ignore")
        return hashlib.sha256(p).hexdigest()[:16]

    def _total_launcher_playtime_sec(self):
        return sum(float(g.get("launcher_playtime_seconds") or 0) for g in self.games)

    def _launcher_platform_stats(self):
        """Distinct games per platform (launcher time ≥ SECRET_ACHIEVEMENT_MIN_SEC) and per-platform launcher seconds."""
        counts = {"Pirated": 0, "Steam": 0, "Xbox": 0}
        seconds = {"Pirated": 0.0, "Steam": 0.0, "Xbox": 0.0}
        m = SECRET_ACHIEVEMENT_MIN_SEC
        for g in self.games:
            lp = float(g.get("launcher_playtime_seconds") or 0)
            plat = self.get_platform(g["path"])
            if plat in seconds:
                seconds[plat] += lp
            if lp >= m and plat in counts:
                counts[plat] += 1
        return counts, seconds

    @staticmethod
    def _secret_achievement_satisfied(kind, need, counts, seconds):
        if kind == "triple_platform":
            return all(counts[p] >= 1 for p in ("Pirated", "Steam", "Xbox"))
        if kind == "pirate_count":
            return counts["Pirated"] >= need
        if kind == "steam_count":
            return counts["Steam"] >= need
        if kind == "xbox_count":
            return counts["Xbox"] >= need
        if kind == "pirated_hours":
            return seconds["Pirated"] >= need
        if kind == "steam_hours":
            return seconds["Steam"] >= need
        if kind == "xbox_hours":
            return seconds["Xbox"] >= need
        return False

    @staticmethod
    def _secret_locked_progress_hint(kind, counts, seconds):
        """Vague progress for locked rows (no exact thresholds)."""
        if kind == "triple_platform":
            return f"Steam {counts['Steam']}, Xbox {counts['Xbox']}, Pirated {counts['Pirated']}"
        if kind == "pirate_count":
            return f"Pirated titles (≥1 min): {counts['Pirated']}"
        if kind == "steam_count":
            return f"Steam titles (≥1 min): {counts['Steam']}"
        if kind == "xbox_count":
            return f"Xbox titles (≥1 min): {counts['Xbox']}"
        if kind == "pirated_hours":
            return f"Pirated hours: {seconds['Pirated'] / 3600.0:.1f}h"
        if kind == "steam_hours":
            return f"Steam hours: {seconds['Steam'] / 3600.0:.1f}h"
        if kind == "xbox_hours":
            return f"Xbox hours: {seconds['Xbox'] / 3600.0:.1f}h"
        return ""

    def _achievement_unlock_labels(self, new_ids):
        """Human-readable names for newly unlocked achievement ids."""
        prof_t = {a[0]: a[2] for a in PROFILE_ACHIEVEMENTS}
        game_t = {a[0]: a[2] for a in GAME_ACHIEVEMENTS}
        sec_map = {x[0]: x[3] for x in SECRET_ACHIEVEMENTS}
        out = []
        for aid in sorted(new_ids):
            if aid in prof_t:
                out.append(prof_t[aid])
            elif aid in sec_map:
                out.append(f"{sec_map[aid]} (secret)")
            elif "__" in aid:
                try:
                    left, gkey = aid.rsplit("__", 1)
                except ValueError:
                    out.append(str(aid))
                    continue
                if left in game_t:
                    gname = None
                    for g in self.games:
                        if self._game_achievement_key(g) == gkey:
                            gname = g["name"]
                            break
                    if gname:
                        out.append(f"{game_t[left]} — {gname}")
                    else:
                        out.append(game_t[left])
                else:
                    out.append(str(aid))
            else:
                out.append(str(aid))
        return out

    def _notify_achievement_unlocks(self, new_ids):
        """Toast + optional system beep when achievements unlock (independent of general toasts)."""
        if not getattr(self, "notify_achievements", True):
            return
        new_ids = set(new_ids)
        labels = self._achievement_unlock_labels(new_ids)
        if not labels:
            return
        secret_id_set = {x[0] for x in SECRET_ACHIEVEMENTS}
        all_secret = new_ids.issubset(secret_id_set)
        if sys.platform == "win32":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass
        body_lines = labels[:8]
        if len(labels) > 8:
            body_lines.append(f"+{len(labels) - 8} more")
        body = "\n".join(body_lines)
        if len(labels) == 1:
            only = next(iter(new_ids))
            if only in secret_id_set:
                Toast(self.root, labels[0], duration=5500, title="Secret unlocked", title_color="#cc88ff")
            else:
                Toast(self.root, labels[0], duration=5500, title="Achievement unlocked")
        elif all_secret:
            title = "Secrets unlocked" if len(new_ids) > 1 else "Secret unlocked"
            Toast(self.root, body, duration=6000, title=title, title_color="#cc88ff")
        else:
            title = "Achievements unlocked" if len(new_ids) > 1 else "Achievement unlocked"
            Toast(self.root, body, duration=5500, title=title)

    def _check_achievements_unlock(self):
        """Run on the main thread; compares launcher-only playtime to thresholds."""
        if not hasattr(self, "games") or self.games is None:
            return
        old_un = self._load_achievements_unlocked()
        unlocked = set(old_un)
        total = self._total_launcher_playtime_sec()
        for aid, need_sec, _title, _desc in PROFILE_ACHIEVEMENTS:
            if aid not in unlocked and total >= need_sec:
                unlocked.add(aid)
        for g in self.games:
            lp = float(g.get("launcher_playtime_seconds") or 0)
            gkey = self._game_achievement_key(g)
            for aid_suffix, need_sec, _title, _desc in GAME_ACHIEVEMENTS:
                aid = f"{aid_suffix}__{gkey}"
                if aid not in unlocked and lp >= need_sec:
                    unlocked.add(aid)
        counts, secs = self._launcher_platform_stats()
        for aid, kind, need, _title, _desc, _hint in SECRET_ACHIEVEMENTS:
            if aid not in unlocked and self._secret_achievement_satisfied(kind, need, counts, secs):
                unlocked.add(aid)
        new_ids = unlocked - old_un
        if not new_ids:
            return
        self._save_achievements_unlocked(unlocked)
        self._notify_achievement_unlocks(new_ids)
        self.update_gamerscore_label()
        if hasattr(self, "achievements_win") and self.achievements_win is not None:
            try:
                if self.achievements_win.winfo_exists():
                    self._refresh_achievements_window()
            except (tk.TclError, AttributeError):
                pass

    def show_achievements(self):
        win = tk.Toplevel(self.root)
        win.title("Achievements")
        win.geometry("760x580")
        win.minsize(520, 400)
        win.configure(bg="#1e1e1e")
        win.transient(self.root)
        self.achievements_win = win

        header = tk.Frame(win, bg="#1e1e1e")
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(
            header,
            text="Launcher achievements",
            font=("", 16, "bold"),
            bg="#1e1e1e",
            fg="#ffffff",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Based on time tracked while playing from this launcher. Steam-imported hours do not count.",
            font=("", 10),
            bg="#1e1e1e",
            fg="#888888",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        canvas = tk.Canvas(win, bg="#1e1e1e", highlightthickness=0)
        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#1e1e1e")
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            try:
                canvas.itemconfigure(inner_id, width=event.width)
            except tk.TclError:
                pass

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 16))
        scroll.pack(side="right", fill="y", pady=(0, 16), padx=(0, 12))

        self._achievements_inner = inner
        self._achievements_canvas = canvas
        self._achievements_header = header
        self._achievements_scrollbar = scroll
        self._achievements_wheel_chrome_bound = False
        self._populate_achievements_frame(inner)
        self._bind_achievements_mousewheel()

        win.protocol("WM_DELETE_WINDOW", lambda: self._close_achievements_window(win))

    def _bind_achievements_mousewheel(self):
        """Scroll the list with the mouse wheel over the header, canvas, scrollbar, or any row (Windows: MouseWheel; Linux: buttons 4/5)."""
        canvas = getattr(self, "_achievements_canvas", None)
        inner = getattr(self, "_achievements_inner", None)
        win = getattr(self, "achievements_win", None)
        if not win or not canvas or not inner:
            return
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return

        def on_wheel(event):
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")

        def bind_wheel_subtree(widget):
            widget.bind("<MouseWheel>", on_wheel)
            widget.bind("<Button-4>", on_wheel)
            widget.bind("<Button-5>", on_wheel)
            for c in widget.winfo_children():
                bind_wheel_subtree(c)

        if not getattr(self, "_achievements_wheel_chrome_bound", False):
            header = getattr(self, "_achievements_header", None)
            if header is not None:
                bind_wheel_subtree(header)
            canvas.bind("<MouseWheel>", on_wheel)
            canvas.bind("<Button-4>", on_wheel)
            canvas.bind("<Button-5>", on_wheel)
            scr = getattr(self, "_achievements_scrollbar", None)
            if scr is not None:
                bind_wheel_subtree(scr)
            inner.bind("<MouseWheel>", on_wheel)
            inner.bind("<Button-4>", on_wheel)
            inner.bind("<Button-5>", on_wheel)
            self._achievements_wheel_chrome_bound = True
        for child in inner.winfo_children():
            bind_wheel_subtree(child)

    def _close_achievements_window(self, win):
        self.achievements_win = None
        self._achievements_wheel_chrome_bound = False
        try:
            win.destroy()
        except tk.TclError:
            pass

    def _refresh_achievements_window(self):
        if not hasattr(self, "_achievements_inner") or self._achievements_inner is None:
            return
        for w in self._achievements_inner.winfo_children():
            w.destroy()
        self._populate_achievements_frame(self._achievements_inner)
        if hasattr(self, "_achievements_canvas") and self._achievements_canvas is not None:
            self._achievements_canvas.update_idletasks()
            self._achievements_canvas.configure(scrollregion=self._achievements_canvas.bbox("all"))
        self._bind_achievements_mousewheel()

    @staticmethod
    def _format_achievement_seconds(seconds):
        s = float(seconds or 0)
        if s <= 0:
            return "0m"
        return Launcher.format_playtime(s)

    def _populate_achievements_frame(self, inner):
        unlocked = self._load_achievements_unlocked()
        total = self._total_launcher_playtime_sec()
        gs_total = self._gamerscore_total()
        sum_lbl = tk.Label(
            inner,
            text=(
                f"Profile launcher playtime: {self._format_achievement_seconds(total)}"
                f"  ·  Gamerscore: {gs_total:,} G"
            ),
            bg="#1e1e1e",
            fg="#c8e7ff",
            font=("", 11, "bold"),
        )
        sum_lbl.pack(anchor="w", pady=(0, 10))

        tk.Label(
            inner,
            text="Profile",
            bg="#1e1e1e",
            fg="#aaaaaa",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(8, 4))

        for aid, need_sec, title, desc in PROFILE_ACHIEVEMENTS:
            ok = aid in unlocked
            gp = GAMERSCORE_PROFILE_POINTS.get(aid, 0)
            row = tk.Frame(inner, bg="#2a2a2a", padx=10, pady=8)
            row.pack(fill="x", pady=3)
            mark = "✓" if ok else "○"
            color = "#ffd77a" if ok else "#666666"
            tk.Label(row, text=mark, bg="#2a2a2a", fg=color, font=("", 12), width=3).pack(side="left")
            txt = tk.Frame(row, bg="#2a2a2a")
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=title, bg="#2a2a2a", fg="#eeeeee" if ok else "#999999", font=("", 11, "bold"), anchor="w").pack(anchor="w")
            tk.Label(txt, text=desc, bg="#2a2a2a", fg="#bbbbbb" if ok else "#777777", font=("", 9), anchor="w", wraplength=620, justify="left").pack(anchor="w")
            need_str = self._format_achievement_seconds(need_sec)
            have_str = self._format_achievement_seconds(total)
            if ok:
                prog = f"Unlocked · {gp} G"
            else:
                prog = f"Requires {need_str} total (have {have_str}) · {gp} G"
            tk.Label(row, text=prog, bg="#2a2a2a", fg="#888888", font=("", 9)).pack(side="right", padx=(8, 0))

        tk.Label(
            inner,
            text="Per game",
            bg="#1e1e1e",
            fg="#aaaaaa",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(16, 4))

        if not self.games:
            tk.Label(inner, text="No games in this profile.", bg="#1e1e1e", fg="#777777", font=("", 10)).pack(anchor="w")
        else:
            for g in sorted(self.games, key=lambda x: x["name"].lower()):
                gkey = self._game_achievement_key(g)
                lp = float(g.get("launcher_playtime_seconds") or 0)
                sec = tk.Frame(inner, bg="#1e1e1e")
                sec.pack(fill="x", pady=(10, 2))
                tk.Label(
                    sec,
                    text=g["name"],
                    bg="#1e1e1e",
                    fg="#ffffff",
                    font=("", 11, "bold"),
                ).pack(anchor="w")
                tk.Label(
                    sec,
                    text=f"Launcher-tracked: {self._format_achievement_seconds(lp)}",
                    bg="#1e1e1e",
                    fg="#888888",
                    font=("", 9),
                ).pack(anchor="w")
                for aid_suffix, need_sec, title, desc in GAME_ACHIEVEMENTS:
                    aid = f"{aid_suffix}__{gkey}"
                    ok = aid in unlocked
                    gp = GAMERSCORE_GAME_SUFFIX_POINTS.get(aid_suffix, 0)
                    row = tk.Frame(inner, bg="#252525", padx=10, pady=6)
                    row.pack(fill="x", pady=2)
                    mark = "✓" if ok else "○"
                    color = "#ffd77a" if ok else "#666666"
                    tk.Label(row, text=mark, bg="#252525", fg=color, font=("", 11), width=3).pack(side="left")
                    txt = tk.Frame(row, bg="#252525")
                    txt.pack(side="left", fill="x", expand=True)
                    tk.Label(txt, text=title, bg="#252525", fg="#eeeeee" if ok else "#999999", font=("", 10, "bold"), anchor="w").pack(anchor="w")
                    tk.Label(txt, text=desc, bg="#252525", fg="#999999", font=("", 8), anchor="w", wraplength=580, justify="left").pack(anchor="w")
                    need_str = self._format_achievement_seconds(need_sec)
                    have_str = self._format_achievement_seconds(lp)
                    if ok:
                        prog = f"Unlocked · {gp} G"
                    else:
                        prog = f"Requires {need_str} (have {have_str}) · {gp} G"
                    tk.Label(row, text=prog, bg="#252525", fg="#777777", font=("", 8)).pack(side="right", padx=(6, 0))

        counts, secs = self._launcher_platform_stats()
        tk.Label(
            inner,
            text="Secret",
            bg="#1e1e1e",
            fg="#cc88ff",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(20, 4))
        tk.Label(
            inner,
            text="Hidden titles until unlocked. Counts use launcher-tracked time only (≥1 min per title).",
            bg="#1e1e1e",
            fg="#776688",
            font=("", 9),
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        for aid, kind, need, title, desc, hint in SECRET_ACHIEVEMENTS:
            ok = aid in unlocked
            gp = GAMERSCORE_SECRET_POINTS.get(aid, 0)
            row = tk.Frame(inner, bg="#2a1f35", padx=10, pady=8)
            row.pack(fill="x", pady=3)
            mark = "✦" if ok else "?"
            color = "#e8b4ff" if ok else "#554455"
            tk.Label(row, text=mark, bg="#2a1f35", fg=color, font=("", 12), width=3).pack(side="left")
            txt = tk.Frame(row, bg="#2a1f35")
            txt.pack(side="left", fill="x", expand=True)
            if ok:
                tk.Label(txt, text=title, bg="#2a1f35", fg="#f0e0ff", font=("", 11, "bold"), anchor="w").pack(anchor="w")
                tk.Label(txt, text=desc, bg="#2a1f35", fg="#cbb0dd", font=("", 9), anchor="w", wraplength=620, justify="left").pack(anchor="w")
                tk.Label(row, text=f"Unlocked · {gp} G", bg="#2a1f35", fg="#9988aa", font=("", 9)).pack(side="right", padx=(8, 0))
            else:
                tk.Label(txt, text="???", bg="#2a1f35", fg="#887788", font=("", 11, "bold"), anchor="w").pack(anchor="w")
                tk.Label(
                    txt,
                    text=f"Secret · theme: {hint} · {self._secret_locked_progress_hint(kind, counts, secs)}",
                    bg="#2a1f35",
                    fg="#665566",
                    font=("", 9),
                    anchor="w",
                    wraplength=620,
                    justify="left",
                ).pack(anchor="w")
                tk.Label(row, text=f"Locked · {gp} G", bg="#2a1f35", fg="#554455", font=("", 9)).pack(side="right", padx=(8, 0))

    @staticmethod
    def _steam_cache_incomplete(loaded):
        """True if we should fetch again (never succeeded, or old failed placeholder)."""
        if not isinstance(loaded, dict):
            return True
        if loaded.get("appid") is not None:
            return False
        desc = (loaded.get("description") or "").strip()
        if desc == "Loading...":
            return True
        if "no info found" in desc.lower():
            return True
        return False

    @staticmethod
    def _safe_profile_segment(profile_name):
        if not profile_name:
            return "profile"
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(profile_name)).strip() or "profile"

    def _cache_file_paths(self, game_name, profile=None):
        """Per-profile cache paths so multiple accounts do not share metadata/images."""
        if profile is None:
            profile = self.current
        safe = game_name.replace(" ", "_")
        prof = self._safe_profile_segment(profile)
        prefix = f"{prof}__{safe}"
        new_json = os.path.join(IMG, f"{prefix}_info.json")
        new_jpg = os.path.join(IMG, f"{prefix}.jpg")
        legacy_json = os.path.join(IMG, f"{safe}_info.json")
        legacy_jpg = os.path.join(IMG, f"{safe}.jpg")
        return new_json, new_jpg, legacy_json, legacy_jpg

    def load(self, fullpath, key=None, default=None):
        if not os.path.exists(fullpath):
            return default
        try:
            with open(fullpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(key) if key else data
        except:
            return default

    def save(self, fullpath, data):
        try:
            os.makedirs(os.path.dirname(fullpath), exist_ok=True)
            with open(fullpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except:
            pass

    def load_user(self):
        user_data = self.load(os.path.join(DIR, "user.json"))
        username = None
        if isinstance(user_data, dict):
            username = user_data.get("username")

        if not isinstance(self.profiles, list) or not self.profiles:
            self.profiles = ["Default"]
            self.save(os.path.join(DIR, "profiles.json"), self.profiles)

        if username and username in self.profiles:
            self.user = username
            self.current = username
            self.load_ui()
        else:
            if username:
                self.save(os.path.join(DIR, "user.json"), {})
            self.user = None
            self.show_login_screen()

    def show_login_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)

        self.root.geometry("430x480")
        self.root.minsize(430, 480)
        self.root.maxsize(430, 480)
        self.root.resizable(False, False)
        self.root.config(bg="#1e1e1e")
        self.center_window()

        tk.Label(self.root, text="Pirate Launcher", font=("", 18, "bold"), bg="#1e1e1e", fg="#ffffff").pack(pady=(30, 10))

        tk.Label(self.root, text="Sign in", font=("", 12, "bold"), bg="#1e1e1e", fg="#dddddd").pack(anchor="w", padx=50, pady=(18, 4))
        users = sorted(self.profiles, key=lambda p: p.lower())
        user_var = tk.StringVar(value=users[0] if users else "")
        combo = ttk.Combobox(self.root, textvariable=user_var, values=users, state="readonly", width=26, font=("", 11))
        combo.pack(pady=6, padx=50)

        def sign_in():
            username = user_var.get().strip()
            if not username or username not in self.profiles:
                messagebox.showwarning("Sign in", "Choose a valid profile.")
                return
            self.current = username
            self.user = username
            self.save(os.path.join(DIR, "user.json"), {"username": username})
            self.load_ui()

        tk.Button(self.root, text="Sign In", command=sign_in,
                  bg="#444466", fg="#ffffff", font=("", 11, "bold"), width=20).pack(pady=10)
        combo.bind("<Return>", lambda e: sign_in())

        tk.Label(self.root, text="New profile", font=("", 12, "bold"), bg="#1e1e1e", fg="#dddddd").pack(anchor="w", padx=50, pady=(16, 4))
        entry = tk.Entry(self.root, font=("", 12), width=28, bg="#2a2a2a", fg="#ffffff", insertbackground="#80d4ff")
        entry.pack(pady=6, padx=50)
        entry.focus()

        def create_account():
            username = entry.get().strip()
            if not username or username.lower() in {"admin", "system", "guest"}:
                messagebox.showwarning("Error", "Invalid or reserved profile name")
                return
            if username in self.profiles:
                messagebox.showwarning("Error", "That profile already exists — pick it above and Sign In.")
                return
            self.profiles.append(username)
            self.save(os.path.join(DIR, "profiles.json"), self.profiles)
            self.current = username
            self.user = username
            self.save(os.path.join(DIR, "user.json"), {"username": username})
            self.save(self.get_settings_path(), {})
            self.load_ui()

        tk.Button(self.root, text="Create profile & sign in", command=create_account,
                  bg="#3d3d5c", fg="#ffffff", font=("", 11, "bold"), width=22).pack(pady=10)
        entry.bind("<Return>", lambda e: create_account())

    def load_ui(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        for w in self.root.winfo_children():
            w.destroy()

        self._last_cover_path = None
        self._cover_photo_ref = None
        self.current_game_idx = None

        settings_path = self.get_settings_path()
        default_settings = {
            "window_geometry": "",
            "last_selected_game": "",
            "last_sort_mode": "Name",
            "last_search_text": "",
            "auto_refresh": True,
            "show_toast": True,
            "notify_achievements": True,
            "enable_logging": False,
            "recently_played_format": "date_time",
            "last_steamid64": "",
            "last_steam_apikey": ""
        }
        settings = self.load(settings_path, default=default_settings) or default_settings

        saved_geom = settings.get("window_geometry")
        if saved_geom and parse_geometry(saved_geom):
            w, h, x, y = parse_geometry(saved_geom)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self._default_main_geometry()

        self.root.minsize(860, 520)
        self.root.config(bg="#1e1e1e")

        self.root.update_idletasks()
        self.root.resizable(True, True)
        self.root.update()
        self.root.resizable(True, True)

        self.auto_refresh = settings.get("auto_refresh", True)
        self.show_toast = settings.get("show_toast", True)
        self.notify_achievements_var = tk.BooleanVar(value=settings.get("notify_achievements", True))
        self.notify_achievements = self.notify_achievements_var.get()
        self.enable_logging = settings.get("enable_logging", False)
        self.recent_format = settings.get("recently_played_format", "date_time")
        self.last_steamid64 = settings.get("last_steamid64", "")
        self.last_steam_apikey = settings.get("last_steam_apikey", "")

        if self.enable_logging:
            logging.basicConfig(
                filename=os.path.join(DIR, "launcher.log"),
                level=logging.INFO,
                format="%(asctime)s - %(message)s"
            )

        self.games = self.load(os.path.join(DIR, f"{self.current}_games.json"), default=[])
        self._migrate_games()

        self.states = {
            g["name"]: {"running": False, "start_time": None, "session_duration": timedelta(0)}
            for g in self.games
        }

        self.cache = {}
        for g in self.games:
            name = g["name"]
            new_json, _new_jpg, legacy_json, _legacy_jpg = self._cache_file_paths(name)
            cache_file = new_json if os.path.exists(new_json) else (legacy_json if os.path.exists(legacy_json) else new_json)
            stale = True
            if os.path.exists(cache_file):
                loaded = self.load(cache_file)
                if isinstance(loaded, dict):
                    loaded.setdefault("image", PLACE)
                    loaded.setdefault("title", name)
                    loaded.setdefault("details", "")
                    loaded.setdefault("description", "No description available")
                    loaded.setdefault("appid", None)
                    self.cache[name] = loaded
                    stale = self._steam_cache_incomplete(loaded)
                else:
                    self.cache[name] = {
                        "image": PLACE, "title": name, "details": "",
                        "description": "Loading...", "appid": None,
                    }
            else:
                self.cache[name] = {
                    "image": PLACE, "title": name, "details": "",
                    "description": "Loading...", "appid": None,
                }
            if stale and name not in self.pending_scrapes:
                self.pending_scrapes.add(name)
                self._schedule_scrape(name, False)

        sid_sync = False
        for g in self.games:
            c = self.cache.get(g["name"])
            if isinstance(c, dict) and c.get("appid") is not None:
                try:
                    new_id = int(c["appid"])
                    if g.get("steam_appid") != new_id:
                        g["steam_appid"] = new_id
                        sid_sync = True
                except (TypeError, ValueError):
                    pass
        if sid_sync:
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(side="top", pady=16, fill="x", padx=28)

        profile_bar = tk.Frame(btn_frame, bg="#1e1e1e")
        profile_bar.pack(side="right", padx=(12, 0))
        self.gamerscore_var = tk.StringVar(value="0 G")
        tk.Label(
            profile_bar,
            textvariable=self.gamerscore_var,
            bg="#1e1e1e",
            fg="#7ec97e",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=(0, 14))
        tk.Label(profile_bar, text="Profile:", bg="#1e1e1e", fg="#aaaaaa", font=("", 10)).pack(side="left", padx=(0, 6))
        self.profile_switch_var = tk.StringVar(value=self.current)
        self.profile_combo = ttk.Combobox(
            profile_bar, textvariable=self.profile_switch_var,
            values=sorted(self.profiles, key=lambda p: p.lower()),
            state="readonly", width=20, font=("", 10))
        self.profile_combo.pack(side="left")
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_combo_switch)

        self.add_var = tk.StringVar(value="Add Game")
        add_options = ["Pirated Games", "Steam Games", "Xbox Games"]
        add_dropdown = tk.OptionMenu(btn_frame, self.add_var, *add_options, command=self.handle_add_dropdown)
        add_dropdown.config(width=14, bg="#333", fg="#fff", relief="raised", font=("", 10))
        add_dropdown.pack(side="left", padx=(0, 10))

        tk.Button(btn_frame, text="Launch", width=12, command=self.launch, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Favorite ★", width=12, command=self.toggle_favorite, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Remove", width=12, command=self.remove, bg="#333", fg="#fff").pack(side="left", padx=4)
        tk.Button(btn_frame, text="Refresh All", width=12, command=self.refresh_all, bg="#333", fg="#fff").pack(side="left", padx=4)

        bottom_frame = tk.Frame(self.root, bg="#121212")
        bottom_frame.pack(side="bottom", fill="x")
        self.status = tk.Label(bottom_frame, text="", anchor="w", bg="#121212", fg="#ccc", font=("", 9))
        self.status.pack(side="left", padx=10, pady=4)
        self.session_status_label = tk.Label(
            bottom_frame,
            text="",
            anchor="e",
            bg="#121212",
            fg="#9fd0ff",
            font=("", 9),
        )
        self.session_status_label.pack(side="right", padx=10, pady=4, fill="x", expand=True)

        main = tk.Frame(self.root, bg="#1e1e1e")
        main.pack(fill="both", expand=True, padx=28, pady=(20, 10))

        sidebar = tk.Frame(main, bg="#1e1e1e", width=200)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        sidebar.grid_propagate(False)

        tk.Label(sidebar, text="Platforms", bg="#1e1e1e", fg="#fff", font=("", 13, "bold")).pack(pady=(15, 8), padx=12, anchor="w")

        self.platform_filter = tk.StringVar(value="All")
        self.platform_buttons = {}

        ICON_SIZE = 24
        self.steam_icon = self.xbox_icon = self.pirate_icon = None
        try:
            steam_path = download_icon_if_missing("steam", ICON_URLS["steam"])
            xbox_path = download_icon_if_missing("xbox", ICON_URLS["xbox"])
            pirate_path = download_icon_if_missing("pirate", ICON_URLS["pirate"])
            self.steam_icon = ImageTk.PhotoImage(Image.open(steam_path).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
            self.xbox_icon = ImageTk.PhotoImage(Image.open(xbox_path).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
            self.pirate_icon = ImageTk.PhotoImage(Image.open(pirate_path).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS))
        except:
            pass

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

        self.list_frame = tk.Frame(main, bg="#1e1e1e")
        self.list_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 18))

        filter_frame = tk.Frame(self.list_frame, bg="#1e1e1e")
        filter_frame.pack(fill="x", pady=(0, 8))

        tk.Label(filter_frame, text="Search:", bg="#1e1e1e", fg="#fff").pack(side="left")
        self.search_var = tk.StringVar(value=settings.get("last_search_text", ""))
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, bg="#2a2a2a", fg="#fff", insertbackground="#fff")
        search_entry.pack(side="left", fill="x", expand=True, padx=(5, 20))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        tk.Label(filter_frame, text="Sort:", bg="#1e1e1e", fg="#fff").pack(side="left")
        self.sort_var = tk.StringVar(value=settings.get("last_sort_mode", "Name"))
        sort_menu = ttk.Combobox(filter_frame, textvariable=self.sort_var,
                                 values=["Name", "Recently Played", "Playtime", "Favorites"],
                                 state="readonly", width=15)
        sort_menu.pack(side="left", padx=(5, 0))
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        columns = ("name", "platform", "playtime", "favorite", "recent")
        self.tree = ttk.Treeview(self.list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Name", command=lambda: self.sort_by_column("name"))
        self.tree.heading("platform", text="Platform", command=lambda: self.sort_by_column("platform"))
        self.tree.heading("playtime", text="Playtime", command=lambda: self.sort_by_column("playtime"))
        self.tree.heading("favorite", text="★", command=lambda: self.sort_by_column("favorite"))
        self.tree.heading("recent", text="Recently Played", command=lambda: self.sort_by_column("recent"))

        self.tree.column("name", width=420, minwidth=140, anchor="w", stretch=True)
        self.tree.column("platform", width=100, minwidth=72, anchor="center", stretch=False)
        self.tree.column("playtime", width=96, minwidth=72, anchor="center", stretch=False)
        self.tree.column("favorite", width=44, minwidth=36, anchor="center", stretch=False)
        self.tree.column("recent", width=160, minwidth=120, anchor="center", stretch=False)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2a2a2a", foreground="#fff",
                        fieldbackground="#2a2a2a", rowheight=42, font=("", 10))
        style.map("Treeview", background=[("selected", "#505050")])

        v_scroll = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self.launch())
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#333", fg="#fff")
        self.context_menu.add_command(label="Toggle Favorite", command=self.toggle_favorite)
        self.context_menu.add_command(label="Refresh Info", command=self.refresh_selected_info)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Remove", command=self.remove)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind("<Up>", self._on_arrow_up)
        self.tree.bind("<Down>", self._on_arrow_down)
        self.tree.focus_set()

        info_frame = tk.Frame(main, bg="#1e1e1e")
        info_frame.grid(row=0, column=2, sticky="nsew", padx=(20, 0))
        self.info_frame = info_frame
        main.grid_columnconfigure(0, weight=0, minsize=200)
        main.grid_columnconfigure(1, weight=2, minsize=300)
        main.grid_columnconfigure(2, weight=1, minsize=260)
        main.grid_rowconfigure(0, weight=1)

        self.cover_canvas = tk.Canvas(info_frame, bg="#1e1e1e", highlightthickness=0, height=200)
        self.cover_canvas.pack(fill="x", padx=20, pady=(18, 10))
        info_frame.bind("<Configure>", self._on_info_frame_configure)

        self.title_canvas = tk.Canvas(info_frame, bg="#1e1e1e", height=50, highlightthickness=0)
        self.title_canvas.pack(pady=(0, 8), fill="x", padx=20)
        self.title_text_id = self.title_canvas.create_text(
            0, 25, text="", anchor="w", font=("", 16, "bold"), fill="#ffffff")

        right_grid = tk.Frame(info_frame, bg="#1e1e1e")
        right_grid.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        self.right_grid = right_grid
        right_grid.grid_rowconfigure(0, weight=1)
        right_grid.grid_rowconfigure(1, weight=1)
        right_grid.grid_columnconfigure(0, weight=1)

        info_container = tk.LabelFrame(
            right_grid, text=" Game Info ", bg="#1e1e1e", fg="#ffffff",
            font=("", 11, "bold"), padx=14, pady=12, bd=1, relief="solid")
        info_container.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        self.details_text = tk.Text(
            info_container,
            bg="#1e1e1e",
            fg="#d0d0d0",
            font=("", 10),
            wrap="word",
            height=6,
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
            bg="#1e1e1e",
            fg="#d0d0d0",
            font=("", 10),
            wrap="word",
            height=6,
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

        self.root.bind("<Return>", lambda e: self.launch())
        self.root.bind("<Delete>", lambda e: self.remove())
        self.root.bind("<Control-f>", lambda e: search_entry.focus_set())
        self.root.bind("<Control-a>", lambda e: self.handle_add_dropdown(self.add_var.get()))

        self.menu()
        self.apply_filters()
        self.restore_last_selection()
        self.show_no_games_placeholder()

        if self.games:
            def _final_force_load():
                children = self.tree.get_children()
                if children and not self.tree.selection():
                    first = children[0]
                    self.tree.selection_set(first)
                    self.tree.focus(first)
                    self.tree.see(first)
                    self.select(None)
            self.root.after(400, _final_force_load)

        self.root.after(100, self.process_queue)
        self.root.after(250, self._apply_info_panel_layout)
        threading.Thread(target=self.global_playtime_tracker, daemon=True).start()
        self.root.after(500, self._check_achievements_unlock)
        self.update_gamerscore_label()

    def center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(50, (sw - w) // 2)
        y = max(50, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _default_main_geometry(self):
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
        except tk.TclError:
            sw, sh = 1280, 800
        w = max(1000, min(1680, int(sw * 0.82)))
        h = max(600, min(960, int(sh * 0.82)))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_info_frame_configure(self, event):
        if not hasattr(self, "info_frame") or event.widget is not self.info_frame:
            return
        if self._panel_resize_job is not None:
            self.root.after_cancel(self._panel_resize_job)
        self._panel_resize_job = self.root.after(100, self._apply_info_panel_layout)

    def _apply_info_panel_layout(self):
        self._panel_resize_job = None
        try:
            self._render_cover_image()
            self._sync_detail_text_heights()
        except (tk.TclError, AttributeError):
            pass

    def _pil_image_to_rgb(self, img):
        img = ImageOps.exif_transpose(img)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (30, 30, 30))
            bg.paste(img, mask=img.split()[3])
            return bg
        if img.mode == "P" and "transparency" in img.info:
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (30, 30, 30))
            bg.paste(img, mask=img.split()[3])
            return bg
        return img.convert("RGB")

    def _render_cover_image(self):
        if not hasattr(self, "cover_canvas") or not self.cover_canvas.winfo_exists():
            return
        path = self._last_cover_path
        self.root.update_idletasks()
        try:
            cw = max(80, (self.cover_canvas.winfo_width() or self.info_frame.winfo_width()) - 8)
        except tk.TclError:
            cw = 360
        max_w = max(120, min(640, cw))
        max_h = max(80, int(max_w / 2.14))

        try:
            if not path or not os.path.isfile(path):
                path = PLACE
            path = os.path.abspath(os.path.normpath(path))
            img = Image.open(path)
            img = self._pil_image_to_rgb(img)
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            self._cover_photo_ref = ImageTk.PhotoImage(img)
        except Exception:
            try:
                img = Image.open(PLACE)
                img = self._pil_image_to_rgb(img)
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                self._cover_photo_ref = ImageTk.PhotoImage(img)
            except Exception:
                return

        self.cover_canvas.delete("all")
        ch = max(90, self._cover_photo_ref.height() + 8)
        self.cover_canvas.config(height=ch)
        w = self.cover_canvas.winfo_width() or max_w + 8
        self.cover_canvas.create_image(
            max(1, w // 2), ch // 2,
            image=self._cover_photo_ref,
            anchor="center",
        )

    def _file_has_image(self, path):
        try:
            return os.path.isfile(path) and os.path.getsize(path) > 512
        except OSError:
            return False

    def _save_steam_header_image(self, session, appid, header_url, dest_jpg):
        if self._file_has_image(dest_jpg):
            return True
        candidates = []
        if header_url:
            candidates.append(header_url.strip())
        candidates.extend(
            [
                f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
            ]
        )
        seen = set()
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            try:
                r = session.get(url, headers=STEAM_IMAGE_HEADERS, timeout=28)
                if r.status_code != 200 or len(r.content) < 512:
                    continue
                img = Image.open(BytesIO(r.content))
                img = self._pil_image_to_rgb(img)
                img.thumbnail((960, 480), Image.LANCZOS)
                os.makedirs(os.path.dirname(dest_jpg), exist_ok=True)
                img.save(dest_jpg, "JPEG", quality=93, optimize=True)
                return True
            except Exception:
                continue
        return False

    def _sync_detail_text_heights(self):
        try:
            if not hasattr(self, "details_text") or not self.right_grid.winfo_exists():
                return
            self.root.update_idletasks()
            rh = self.right_grid.winfo_height()
            if rh < 70:
                return
            fh = tkfont.Font(font=self.details_text.cget("font")).metrics("linespace") or 14
            usable = max(0, rh - 24)
            lines = max(3, min(60, usable // (2 * max(fh, 1))))
            self.details_text.configure(height=lines)
            self.desc.configure(height=lines)
        except (tk.TclError, AttributeError):
            pass

    def persist_current_profile_state(self):
        """Save window layout, UI preferences, and library for the active profile."""
        try:
            if not hasattr(self, "sort_var"):
                return
            if not self.root.winfo_exists():
                return
            settings_path = self.get_settings_path()
            settings = self.load(settings_path, default={})
            try:
                settings["window_geometry"] = self.root.geometry()
            except tk.TclError:
                pass
            sel = self.tree.selection() if hasattr(self, "tree") else ()
            if sel:
                try:
                    idx = int(sel[0])
                    if idx < len(self.games):
                        settings["last_selected_game"] = self.games[idx]["name"]
                except (ValueError, IndexError, tk.TclError):
                    pass
            settings["last_sort_mode"] = self.sort_var.get()
            settings["last_search_text"] = self.search_var.get()
            if hasattr(self, "notify_achievements_var"):
                settings["notify_achievements"] = self.notify_achievements_var.get()
            else:
                settings["notify_achievements"] = getattr(self, "notify_achievements", True)
            self.save(settings_path, settings)
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
        except Exception:
            pass

    def on_close(self):
        self.persist_current_profile_state()
        self.root.destroy()

    def reset_window_to_default(self):
        self._default_main_geometry()
        self.root.update_idletasks()
        self.root.resizable(True, True)
        settings_path = self.get_settings_path()
        settings = self.load(settings_path, default={})
        if "window_geometry" in settings:
            del settings["window_geometry"]
        self.save(settings_path, settings)
        self.root.after(100, self._apply_info_panel_layout)
        Toast(self.root, "Window reset to a default size that fits your screen", 3000)

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
            if "steam_imported_seconds" not in g:
                g["steam_imported_seconds"] = 0
            if "launcher_playtime_seconds" not in g or not isinstance(g.get("launcher_playtime_seconds"), (int, float)):
                pt = float(g.get("playtime") or 0)
                imp = float(g.get("steam_imported_seconds") or 0)
                g["launcher_playtime_seconds"] = max(0.0, pt - imp)
                changed = True
            if "steam_appid" not in g:
                g["steam_appid"] = None
                changed = True
        if changed:
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)

    def restore_last_selection(self):
        settings_path = self.get_settings_path()
        settings = self.load(settings_path, default={})
        last_game_name = settings.get("last_selected_game")
        if not last_game_name:
            return
        for idx, g in enumerate(self.games):
            if g["name"] == last_game_name:
                iid = str(idx)
                if iid in self.tree.get_children():
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                    self.select(None)
                break

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

        self.update_status_bar()

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

        if not self.tree.get_children():
            self.current_game_idx = None
            self.show(PLACE, "No game selected", "", "")

        self.show_no_games_placeholder()

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

    def refresh_selected_info(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        name = self.games[idx]["name"]
        self._schedule_scrape(name, True)

    def refresh_all(self):
        for g in self.games:
            self._schedule_scrape(g["name"], True)

    def _schedule_scrape(self, name, force=False):
        profile = self.current

        def run():
            try:
                self.scrape_and_cache(name, force, profile)
            finally:
                self.pending_scrapes.discard(name)

        threading.Thread(target=run, daemon=True).start()

    def scrape_and_cache(self, name, force=False, profile=None):
        if profile is None:
            profile = self.current
        new_json, _new_jpg, legacy_json, _legacy_jpg = self._cache_file_paths(name, profile)
        read_path = new_json if os.path.exists(new_json) else legacy_json
        if os.path.exists(read_path) and not force:
            loaded = self.load(read_path)
            if isinstance(loaded, dict) and not self._steam_cache_incomplete(loaded):
                loaded.setdefault("image", PLACE)
                loaded.setdefault("title", name)
                loaded.setdefault("details", "")
                loaded.setdefault("description", "No description available")
                loaded.setdefault("appid", None)
                if profile == self.current:
                    self.cache[name] = loaded
                if read_path == legacy_json and not os.path.exists(new_json):
                    self.save(new_json, loaded)
                return

        try:
            info = self.scrape(name, profile)
            self.save(new_json, info)
            if profile != self.current:
                return
            self.cache[name] = info
            aid = info.get("appid")
            if aid is not None:
                for g in self.games:
                    if g["name"] == name:
                        try:
                            g["steam_appid"] = int(aid)
                        except (TypeError, ValueError):
                            pass
                        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
                        break
            self.update_queue.put(self.apply_filters)

            selected = self.tree.selection()
            if selected:
                try:
                    sel_idx = int(selected[0])
                    if sel_idx < len(self.games) and self.games[sel_idx]["name"] == name:
                        self.update_queue.put(lambda: self.select(None))
                except Exception:
                    pass
        except Exception:
            pass

    def _resolve_steam_appid(self, session, display_name):
        """Resolve a game title to a Steam app id (community search, then store search)."""
        key = quote(display_name, safe="")
        try:
            r = session.get(
                f"https://steamcommunity.com/actions/SearchApps/{key}",
                headers=STEAM_COMMUNITY_HEADERS,
                timeout=18,
            )
            if r.status_code == 200:
                apps = r.json()
                if isinstance(apps, list) and apps:
                    app = next(
                        (a for a in apps if (a.get("name") or "").lower() == display_name.lower()),
                        apps[0],
                    )
                    raw = app.get("appid")
                    if raw is not None:
                        return int(str(raw))
        except (requests.RequestException, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass

        try:
            r = session.get(
                "https://store.steampowered.com/api/storesearch/",
                params={"term": display_name, "cc": "US", "l": "en"},
                headers=STEAM_STORE_HEADERS,
                timeout=18,
            )
            if r.status_code != 200:
                return None
            payload = r.json()
            items = payload.get("items") or []
            if not items:
                return None
            pick = next(
                (it for it in items if (it.get("name") or "").lower() == display_name.lower()),
                items[0],
            )
            raw = pick.get("id")
            if raw is not None:
                return int(str(raw))
        except (requests.RequestException, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass
        return None

    def scrape(self, name, profile=None):
        if profile is None:
            profile = self.current
        _nj, new_jpg, _legacy_json, legacy_img = self._cache_file_paths(name, profile)
        for p in (new_jpg, legacy_img):
            try:
                if os.path.isfile(p) and os.path.getsize(p) < 400:
                    os.remove(p)
            except OSError:
                pass
        has_art = self._file_has_image(new_jpg) or self._file_has_image(legacy_img)

        session = requests.Session()
        try:
            appid = self._resolve_steam_appid(session, name)
            if appid is None:
                return {
                    "image": PLACE,
                    "title": name,
                    "details": "",
                    "description": "No Steam match for this title. Try renaming the game or use Refresh Info.",
                    "appid": None,
                }

            r = session.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": appid, "cc": "us", "l": "en"},
                headers=STEAM_STORE_HEADERS,
                timeout=20,
            )
            if r.status_code != 200:
                return {
                    "image": PLACE,
                    "title": name,
                    "details": "",
                    "description": f"Steam store returned HTTP {r.status_code}. Try again later.",
                    "appid": None,
                }

            try:
                parsed = r.json()
            except json.JSONDecodeError:
                return {
                    "image": PLACE,
                    "title": name,
                    "details": "",
                    "description": "Steam store returned invalid JSON.",
                    "appid": None,
                }

            block = (parsed or {}).get(str(appid)) or {}
            if not block.get("success"):
                return {
                    "image": PLACE,
                    "title": name,
                    "details": "",
                    "description": "Steam has no store details for this app (unlisted or removed).",
                    "appid": appid,
                }

            data = block.get("data") or {}
            if not data:
                return {
                    "image": PLACE,
                    "title": name,
                    "details": "",
                    "description": "Empty response from Steam store API.",
                    "appid": appid,
                }

            title = data.get("name", name)
            release = (data.get("release_date") or {}).get("date", "Unknown")
            developers = ", ".join(data.get("developers") or ["Unknown"])
            genres = ", ".join([g["description"] for g in data.get("genres") or []])
            short_desc = data.get("short_description") or "No description available."
            details_lines = []
            if developers and developers != "Unknown":
                details_lines.append(f"Developer: {developers}")
            if genres:
                details_lines.append(f"Genres: {genres}")
            if release and release != "Unknown":
                details_lines.append(f"Release Date: {release}")
            header_img = data.get("header_image")

            if not has_art:
                self._save_steam_header_image(session, appid, header_img, new_jpg)

            art = new_jpg if self._file_has_image(new_jpg) else (
                legacy_img if self._file_has_image(legacy_img) else PLACE
            )
            if art != PLACE:
                art = os.path.abspath(art)
            return {
                "image": art,
                "title": title,
                "details": "\n".join(details_lines),
                "description": short_desc,
                "appid": appid,
            }
        except (requests.RequestException, ValueError, TypeError, OSError) as e:
            return {
                "image": PLACE,
                "title": name,
                "details": "",
                "description": f"Could not reach Steam ({type(e).__name__}). Check your connection and try Refresh All.",
                "appid": None,
            }

    def show(self, img_path, title, details, desc):
        try:
            if img_path:
                p = os.path.abspath(os.path.normpath(str(img_path)))
                self._last_cover_path = p if os.path.isfile(p) else PLACE
            else:
                self._last_cover_path = PLACE
        except (TypeError, OSError):
            self._last_cover_path = PLACE
        self._render_cover_image()

        self.title_canvas.itemconfig(self.title_text_id, text="")
        self.root.after(120, lambda: self.start_title_scroll(title))
        self.root.after(40, self._apply_info_panel_layout)

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

    def start_title_scroll(self, full_text):
        self.title_canvas.update_idletasks()
        cw = self.title_canvas.winfo_width()
        display_width = max(220, cw) if cw > 20 else 460
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
                try:
                    task()
                except tk.TclError:
                    pass
                except Exception:
                    logging.exception("update_queue task failed")
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def select(self, event):
        sel = self.tree.selection()
        if not sel:
            self.show(PLACE, "No game selected", "", "")
            return
        try:
            idx = int(sel[0])
        except:
            return
        if idx >= len(self.games):
            return
        self.current_game_idx = idx
        game = self.games[idx]

        cache_info = self.cache.get(game["name"], {
            "image": PLACE,
            "title": game["name"],
            "details": "",
            "description": "Loading... (refresh if needed)",
            "appid": None
        })
        self.show(
            cache_info.get("image", PLACE),
            cache_info.get("title", game["name"]),
            cache_info.get("details", ""),
            cache_info.get("description", "Loading...")
        )

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
                    state['session_duration'] = datetime.now() - state['start_time']
                    if not active_game or state['start_time'] > (self.states.get(active_game, {}).get('start_time') or datetime.min):
                        active_game = game['name']
                        active_duration = state['session_duration']
                else:
                    if state['running']:
                        duration_sec = (datetime.now() - state['start_time']).total_seconds()
                        game['playtime'] += duration_sec
                        game['launcher_playtime_seconds'] = float(game.get('launcher_playtime_seconds') or 0) + duration_sec
                        state['running'] = False
                        state['start_time'] = None
                        state['session_duration'] = timedelta(0)
                        updated = True
                        if self.show_toast and duration_sec > 0:
                            Toast(self.root, f"Playtime added for {game['name']}: +{self.format_playtime(duration_sec)}")
                        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
                        self.update_queue.put(self._check_achievements_unlock)

            if updated:
                self.update_queue.put(self.apply_filters)

            if active_game:
                g = next((x for x in self.games if x["name"] == active_game), None)
                dur_sec = active_duration.total_seconds()
                session_str = self.format_duration(dur_sec)
                if g is not None:
                    base = float(g.get("playtime") or 0)
                    total_live = base + dur_sec
                    total_str = self.format_playtime(total_live)
                    text = (
                        f"Playing: {active_game}  |  This session: {session_str}  |  "
                        f"Total (library): {total_str}"
                    )
                else:
                    text = f"Playing: {active_game}  |  This session: {session_str}"

                def safe_set_playing():
                    if self.session_status_label and self.session_status_label.winfo_exists():
                        self.session_status_label.config(text=text)

                self.update_queue.put(safe_set_playing)
            else:
                def safe_clear():
                    if self.session_status_label and self.session_status_label.winfo_exists():
                        self.session_status_label.config(text="")
                self.update_queue.put(safe_clear)

            time.sleep(1)

    def update_status_bar(self):
        if not self.status:
            return
        total = self.format_total_playtime()
        text = f"Profile: @{self.current} | {len(self.games)} game(s) | Showing: {len(self.tree.get_children())} | Playtime: {total}"
        self.status.config(text=text)

    def format_total_playtime(self):
        total_sec = sum(g.get("playtime", 0) for g in self.games)
        h = int(total_sec // 3600)
        m = int((total_sec % 3600) // 60)
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m"
        else:
            return "0m"

    def show_no_games_placeholder(self):
        if hasattr(self, 'no_games_label') and self.no_games_label:
            self.no_games_label.destroy()
        if len(self.games) == 0 and hasattr(self, 'list_frame'):
            self.no_games_label = tk.Label(
                self.list_frame,
                text="No games in your library yet\nClick 'Add Game' below to get started ↓",
                bg="#1e1e1e",
                fg="#888888",
                font=("", 16),
                justify="center"
            )
            self.no_games_label.place(relx=0.5, rely=0.5, anchor="center")

    def hide_no_games_placeholder(self):
        if hasattr(self, 'no_games_label') and self.no_games_label:
            self.no_games_label.destroy()
            self.no_games_label = None

    def add_from_dir(self, initial_dir):
        if not os.path.exists(initial_dir):
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
            "launcher_playtime_seconds": 0.0,
            "last_launch": None,
            "favorite": False,
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steam_imported_seconds": 0,
            "steam_appid": None,
        }
        self.games.append(new_game)
        self.states[new_game['name']] = {"running": False, "start_time": None, "session_duration": timedelta(0)}
        self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
        self.cache[name] = {"image": PLACE, "title": name, "details": "", "description": "Loading...", "appid": None}
        self._schedule_scrape(name, False)
        self.apply_filters()
        self.update_status_bar()
        self.hide_no_games_placeholder()
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
            self.update_status_bar()
            self.show_no_games_placeholder()
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

    def _sync_notify_achievements(self):
        self.notify_achievements = self.notify_achievements_var.get()

    def menu(self):
        menubar = tk.Menu(self.root, bg="#333", fg="#fff")
        settings_menu = tk.Menu(menubar, tearoff=0, bg="#333", fg="#fff")
        menubar.add_cascade(label="Settings", menu=settings_menu)

        settings_menu.add_checkbutton(
            label="Achievement notifications",
            variable=self.notify_achievements_var,
            command=self._sync_notify_achievements,
        )
        settings_menu.add_separator()

        achievements_menu = tk.Menu(menubar, tearoff=0, bg="#333", fg="#fff")
        achievements_menu.add_command(label="View achievements", command=self.show_achievements)
        menubar.add_cascade(label="Achievements", menu=achievements_menu)

        data_menu = tk.Menu(settings_menu, tearoff=0, bg="#333", fg="#fff")
        settings_menu.add_cascade(label="Data & Sync", menu=data_menu)
        data_menu.add_command(label="Reset Playtime (Current Profile)", command=self.reset_playtime)
        data_menu.add_command(label="Import Steam Playtime & Last Played...", command=self.show_steam_sync_dialog)
        data_menu.add_command(label="Clear Saved Steam Playtime Import", command=self.clear_steam_import_watermark)
        data_menu.add_separator()
        data_menu.add_command(label="Create New Profile", command=self.new_profile)
        data_menu.add_command(label="Switch Profile", command=self.switch_profile)
        data_menu.add_command(label="Delete Profile", command=self.del_profile)
        data_menu.add_separator()
        data_menu.add_command(label="Clear All Games (Current Profile)", command=self.clear_games)
        data_menu.add_command(label="Clear All Launcher Data", command=self.clear_all)
        data_menu.add_separator()
        data_menu.add_command(label="Reset Window to Default Size", command=self.reset_window_to_default)

        settings_menu.add_separator()

        tools_menu = tk.Menu(settings_menu, tearoff=0, bg="#333", fg="#fff")
        settings_menu.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Backup downloads…", command=self.open_download_manager)

        settings_menu.add_separator()
        settings_menu.add_command(label="Sign Out", command=self.sign_out)

        format_menu = tk.Menu(settings_menu, tearoff=0, bg="#333", fg="#fff")
        settings_menu.add_cascade(label="Recently Played Format", menu=format_menu)
        format_menu.add_command(label="Date & Time",
                               command=lambda: self.set_recent_format("date_time"))
        format_menu.add_command(label="Time Ago",
                               command=lambda: self.set_recent_format("time_ago"))

        self.root.config(menu=menubar)

    def open_download_manager(self):
        DownloadManagerWindow(self)

    def reset_playtime(self):
        if messagebox.askyesno("Reset Playtime", "Reset ALL playtime to 0 for the current profile?\nThis cannot be undone."):
            for game in self.games:
                game["playtime"] = 0.0
                game["launcher_playtime_seconds"] = 0.0
                game["steam_imported_seconds"] = 0
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self._save_achievements_unlocked(set())
            self.apply_filters()
            self.update_status_bar()
            self.update_gamerscore_label()
            Toast(self.root, "Playtime reset to 0 for all games in this profile", 4000)

    def clear_steam_import_watermark(self):
        if messagebox.askyesno("Clear Steam Import Data", "This will reset the saved Steam playtime reference for all games to 0.\nNext import will pull full current Steam playtime again.\nContinue?"):
            for game in self.games:
                game["steam_imported_seconds"] = 0
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self.apply_filters()
            Toast(self.root, "Steam import reference cleared — next sync will import full playtime", 6000)

    def show_steam_sync_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Import Steam Playtime & Last Played")
        dialog.geometry("560x480")
        dialog.minsize(400, 380)
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1e1e1e")

        btn_frame = tk.Frame(dialog, bg="#1e1e1e")
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=14)

        main = tk.Frame(dialog, bg="#1e1e1e")
        main.pack(fill="both", expand=True, padx=28, pady=(16, 8))

        tk.Label(
            main,
            text="Steam Playtime & Last Played",
            font=("", 15, "bold"),
            bg="#1e1e1e",
            fg="#ffffff",
        ).pack(anchor="w", pady=(0, 12))

        tk.Label(main, text="Your SteamID64 (17 digits):", bg="#1e1e1e", fg="#e0e0e0", font=("", 11)).pack(anchor="w")
        steamid_entry = tk.Entry(main, font=("", 11), bg="#2a2a2a", fg="#ffffff", insertbackground="#80bfff")
        steamid_entry.insert(0, self.last_steamid64)
        steamid_entry.pack(pady=(4, 6), fill="x")

        id_help = tk.Label(
            main,
            text="Don't know your SteamID64? Click here to find it →",
            fg="#4da6ff",
            bg="#1e1e1e",
            cursor="hand2",
            font=("", 10, "underline"),
        )
        id_help.pack(anchor="w", pady=(0, 14))
        id_help.bind("<Button-1>", lambda e: webbrowser.open_new("https://steamid.io/"))

        tk.Label(main, text="Steam Web API Key:", bg="#1e1e1e", fg="#e0e0e0", font=("", 11)).pack(anchor="w")
        apikey_entry = tk.Entry(main, font=("", 11), bg="#2a2a2a", fg="#ffffff", insertbackground="#80bfff")
        apikey_entry.insert(0, self.last_steam_apikey)
        apikey_entry.pack(pady=(4, 6), fill="x")

        api_help = tk.Label(
            main,
            text="Get your free Steam Web API Key here →",
            fg="#4da6ff",
            bg="#1e1e1e",
            cursor="hand2",
            font=("", 10, "underline"),
        )
        api_help.pack(anchor="w")
        api_help.bind("<Button-1>", lambda e: webbrowser.open_new("https://steamcommunity.com/dev/apikey"))

        tk.Label(
            main,
            text="(You need to be logged in to Steam in your browser to register a key)",
            bg="#1e1e1e",
            fg="#888888",
            font=("", 9),
        ).pack(anchor="w", pady=(6, 0))

        hint_label = tk.Label(
            main,
            text="Imports total playtime and last played (Steam last-play time) into this launcher. "
                 "If the launcher already has a newer last-played time, it is kept.",
            bg="#1e1e1e",
            fg="#aaaaaa",
            font=("", 9),
            wraplength=420,
            justify="left",
        )
        hint_label.pack(anchor="w", fill="x", pady=(12, 0))

        status_var = tk.StringVar(value="")
        status_label = tk.Label(
            main,
            textvariable=status_var,
            bg="#1e1e1e",
            fg="#88ff88",
            wraplength=420,
            justify="center",
            font=("", 10),
        )
        status_label.pack(fill="x", pady=(12, 0))

        wrap_labels = [hint_label, status_label]
        wrap_job = [None]

        def apply_steam_dialog_wrap(_event=None):
            try:
                w = max(240, dialog.winfo_width() - 80)
            except tk.TclError:
                return
            for lb in wrap_labels:
                try:
                    lb.config(wraplength=w)
                except tk.TclError:
                    pass

        def schedule_wrap(event=None):
            if wrap_job[0] is not None:
                try:
                    dialog.after_cancel(wrap_job[0])
                except tk.TclError:
                    pass
            wrap_job[0] = dialog.after(60, run_wrap)

        def run_wrap():
            wrap_job[0] = None
            apply_steam_dialog_wrap()

        dialog.bind("<Configure>", schedule_wrap)
        dialog.after(80, run_wrap)

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
            settings_path = self.get_settings_path()
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
            main.update_idletasks()
            run_wrap()

        tk.Button(
            btn_frame,
            text="Import / Sync Playtime",
            command=do_sync,
            bg="#4a6a8a",
            fg="#ffffff",
            activebackground="#5a7a9a",
            font=("", 11, "bold"),
            width=22,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_frame,
            text="Force Full Import",
            command=lambda: self.sync_steam_playtime(
                steamid_entry.get().strip(), apikey_entry.get().strip(), force_full=True
            ),
            bg="#6a4a8a",
            fg="#ffffff",
            activebackground="#7a5a9a",
            font=("", 11, "bold"),
            width=22,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg="#333333",
            fg="#cccccc",
            font=("", 10),
            width=12,
        ).pack(side="right", padx=4)

    @staticmethod
    def _norm_game_title(s):
        if not s:
            return ""
        s = unicodedata.normalize("NFKC", str(s)).lower()
        for ch in "™®":
            s = s.replace(ch, "")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _resolved_steam_appid(self, game):
        raw = game.get("steam_appid")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        name = game.get("name", "")
        cached = self.cache.get(name, {}) if hasattr(self, "cache") else {}
        aid = cached.get("appid") if isinstance(cached, dict) else None
        if aid is not None:
            try:
                return int(aid)
            except (TypeError, ValueError):
                pass
        return None

    def _launcher_game_matches_steam_row(self, game, api_game):
        """Match library row to Steam GetOwnedGames entry (appid preferred, then fuzzy name)."""
        api_appid = api_game.get("appid")
        if api_appid is not None:
            try:
                api_appid = int(api_appid)
            except (TypeError, ValueError):
                api_appid = None
        gid = self._resolved_steam_appid(game)
        if api_appid is not None and gid is not None and gid == api_appid:
            return True

        api_name = (api_game.get("name") or "").strip()
        ln = (game.get("name") or "").strip()
        if not api_name or not ln:
            return False

        na = self._norm_game_title(ln)
        nb = self._norm_game_title(api_name)
        if na and nb:
            if na == nb:
                return True
            if len(na) >= 4 and (na in nb or nb in na):
                return True
            if difflib.SequenceMatcher(None, na, nb).ratio() >= 0.86:
                return True

        ll = ln.lower()
        al = api_name.lower()
        if "counter-strike" in ll and "counter-strike" in al:
            return True
        if ("cs2" in ll or "cs:go" in ll) and ("counter-strike 2" in al or "cs2" in al):
            return True
        return False

    @staticmethod
    def _steam_rtime_to_last_launch_str(api_game):
        """Steam GetOwnedGames may include rtime_last_played (unix seconds). Maps to our last_launch format."""
        rtime = api_game.get("rtime_last_played")
        if rtime is None:
            return None
        try:
            ts = int(rtime)
        except (TypeError, ValueError):
            return None
        if ts <= 0:
            return None
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _merge_last_launch_prefer_newer(current, steam_str):
        """Keep the more recent of launcher-tracked last_launch and Steam last played."""
        if not steam_str:
            return current
        if not current:
            return steam_str
        try:
            a = datetime.strptime(current, "%Y-%m-%d %H:%M:%S")
            b = datetime.strptime(steam_str, "%Y-%m-%d %H:%M:%S")
            return steam_str if b > a else current
        except (ValueError, TypeError):
            return steam_str

    def sync_steam_playtime(self, steamid, api_key, force_full=False):
        # force_full kept for UI compatibility; both paths now set playtime to Steam totals for matches.
        _ = force_full
        url = (
            f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
            f"?key={api_key}&steamid={steamid}&format=json&include_appinfo=1&include_played_free_games=1"
        )
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                return f"Steam API error (HTTP {r.status_code}) — check your key or internet"
            data = r.json()
            if "response" not in data or "games" not in data["response"]:
                msg = data.get("response", {}).get("message", "Unknown error")
                if "profile" in str(msg).lower() and "private" in str(msg).lower():
                    return "Steam profile must be public (or Games details visible) to list owned games"
                return f"Steam returned: {msg}"

            games_from_steam = data["response"]["games"]
            if not games_from_steam:
                return "No games found in Steam library"

            updated = 0
            for api_game in games_from_steam:
                api_name = api_game.get("name", "").strip()
                if not api_name:
                    continue
                pt_min = api_game.get("playtime_forever", 0) or 0
                try:
                    api_seconds = float(pt_min) * 60.0
                except (TypeError, ValueError):
                    continue

                for game in self.games:
                    if not self._launcher_game_matches_steam_row(game, api_game):
                        continue
                    game["playtime"] = round(api_seconds, 2)
                    game["steam_imported_seconds"] = int(round(api_seconds))
                    aid = api_game.get("appid")
                    if aid is not None:
                        try:
                            game["steam_appid"] = int(aid)
                        except (TypeError, ValueError):
                            pass
                    steam_ls = self._steam_rtime_to_last_launch_str(api_game)
                    if steam_ls:
                        game["last_launch"] = self._merge_last_launch_prefer_newer(
                            game.get("last_launch"), steam_ls
                        )
                    updated += 1
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
                return (
                    f"Success! Updated playtime and last played (from Steam) for {updated} game(s). "
                    "Matches use Steam app id or fuzzy title. "
                    "Last played uses Steam when newer than your launcher record."
                )
            return (
                "No launcher games matched your Steam library. "
                "Use the exact Steam store name, refresh game info first, or rename the entry to match Steam."
            )
        except requests.RequestException as e:
            return f"Network / API error: {str(e)}"
        except Exception:
            return "Unexpected error during sync"

    def set_recent_format(self, fmt):
        self.recent_format = fmt
        settings_path = self.get_settings_path()
        settings = self.load(settings_path, default={})
        settings["recently_played_format"] = fmt
        self.save(settings_path, settings)
        self.apply_filters()
        Toast(self.root, f"Recently Played format set to: {'Date & Time' if fmt == 'date_time' else 'Time Ago'}", 2500)

    def sign_out(self):
        self.persist_current_profile_state()
        user_json = os.path.join(DIR, "user.json")
        if os.path.exists(user_json):
            os.remove(user_json)
        self.user = None
        self.show_login_screen()

    def _on_profile_combo_switch(self, event=None):
        name = self.profile_switch_var.get()
        if name == self.current:
            return
        self.switch_profile(name)

    def new_profile(self):
        name = simpledialog.askstring("New Profile", "Profile name:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name.lower() in {"admin", "system", "guest"}:
            messagebox.showwarning("Error", "Invalid or reserved profile name")
            return
        if name in self.profiles:
            messagebox.showwarning("Error", "Profile already exists — use Switch Profile or the profile menu.")
            return
        self.profiles.append(name)
        self.save(os.path.join(DIR, "profiles.json"), self.profiles)
        self.switch_profile(name)

    def switch_profile(self, name=None):
        if not name:
            name = simpledialog.askstring(
                "Switch Profile",
                "Enter profile name:\n" + "\n".join(sorted(self.profiles, key=lambda p: p.lower())),
            )
            if not name:
                if hasattr(self, "profile_switch_var"):
                    self.profile_switch_var.set(self.current)
                return
        name = name.strip()
        if not name:
            if hasattr(self, "profile_switch_var"):
                self.profile_switch_var.set(self.current)
            return
        if name not in self.profiles:
            messagebox.showwarning("Profile", f"No profile named '{name}'.")
            if hasattr(self, "profile_switch_var"):
                self.profile_switch_var.set(self.current)
            return
        if name == self.current:
            return
        self.persist_current_profile_state()
        self.current = name
        self.user = name
        self.save(os.path.join(DIR, "user.json"), {"username": name})
        self.load_ui()

    def del_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("Cannot Delete", "Cannot delete the last profile.")
            return
        name = simpledialog.askstring("Delete Profile", "Profile to delete:\n" + "\n".join([p for p in self.profiles if p != self.current]))
        if name and name in self.profiles and name != self.current:
            if messagebox.askyesno("Confirm", f"Delete profile '{name}' and its data?"):
                self.profiles.remove(name)
                for file_suffix in ["_games.json", "_settings.json", "_achievements.json"]:
                    path = os.path.join(DIR, f"{name}{file_suffix}")
                    if os.path.exists(path):
                        os.remove(path)
                self.save(os.path.join(DIR, "profiles.json"), self.profiles)
                messagebox.showinfo("Deleted", f"Profile '{name}' deleted.")

    def clear_games(self):
        if messagebox.askyesno("Clear Games", "Remove all games from current profile?\nPlaytime and other data will be lost."):
            self.games = []
            self.states = {}
            self.save(os.path.join(DIR, f"{self.current}_games.json"), self.games)
            self._save_achievements_unlocked(set())
            self.apply_filters()
            self.update_status_bar()
            self.update_gamerscore_label()
            self.show_no_games_placeholder()
            Toast(self.root, "All games cleared from this profile", 3500)

    def clear_all(self):
        if messagebox.askyesno("DANGER ZONE", "Delete ALL launcher data?\nThis removes all profiles, games, cache, settings — irreversible!"):
            for file in os.listdir(DIR):
                if file.endswith(".json") or file.endswith(".log"):
                    os.remove(os.path.join(DIR, file))
            os.makedirs(IMG, exist_ok=True)
            self.profiles = ["Default"]
            self.current = "Default"
            self.user = None
            self.save(os.path.join(DIR, "profiles.json"), self.profiles)
            self.save(os.path.join(DIR, "user.json"), {})
            self.show_login_screen()
            Toast(self.root, "All data cleared — fresh start", 5000)

if __name__ == "__main__":
    root = tk.Tk()
    app = Launcher(root)
    root.mainloop()