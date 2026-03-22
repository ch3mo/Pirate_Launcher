"""
Pirate Launcher — shared helpers: atomic JSON, session logs, plugins, exports, seasonal, captain's log.
"""
from __future__ import annotations

import csv
import hashlib
import re
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# --- Atomic JSON ---


def atomic_write_json(path: str, data: Any, indent: int = 4) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


# --- Portable paths ---


def resolve_portable_path(base_dir: str, stored: str) -> str:
    """If stored is relative, resolve under base_dir."""
    if not stored:
        return stored
    p = Path(stored)
    if not p.is_absolute():
        return str((Path(base_dir) / p).resolve())
    return str(p)


def to_portable_path(base_dir: str, absolute: str) -> str:
    """Store as relative if under base_dir."""
    try:
        abs_p = Path(absolute).resolve()
        base = Path(base_dir).resolve()
        try:
            rel = abs_p.relative_to(base)
            return str(rel).replace("\\", "/")
        except ValueError:
            return str(abs_p)
    except (OSError, ValueError):
        return absolute


# --- Session log (JSON lines) ---


def session_log_path(components_dir: str, profile: str) -> str:
    safe = re_safe_segment(profile)
    return os.path.join(components_dir, f"{safe}_sessions.jsonl")


def append_session_record(
    components_dir: str,
    profile: str,
    record: Dict[str, Any],
) -> None:
    path = session_log_path(components_dir, profile)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def export_sessions_csv(components_dir: str, profile: str, dest_csv: str) -> int:
    path = session_log_path(components_dir, profile)
    if not os.path.isfile(path):
        return 0
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return 0
    keys = sorted({k for r in rows for k in r.keys()})
    with open(dest_csv, "w", encoding="utf-8", newline="") as out:
        w = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def re_safe_segment(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip() or "profile"
    return s


# --- Captain's log ---


def captains_log_path(components_dir: str, profile: str) -> str:
    return os.path.join(components_dir, f"{re_safe_segment(profile)}_captains_log.json")


def append_captains_entry(components_dir: str, profile: str, day: str, sentence: str) -> None:
    path = captains_log_path(components_dir, profile)
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    data[day] = sentence.strip()
    atomic_write_json(path, data)


# --- Seasonal / weekly challenges (local) ---


def seasonal_state_path(components_dir: str, profile: str) -> str:
    return os.path.join(components_dir, f"{re_safe_segment(profile)}_seasonal.json")


def iso_week_id(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def load_seasonal(components_dir: str, profile: str) -> Dict[str, Any]:
    p = seasonal_state_path(components_dir, profile)
    if not os.path.isfile(p):
        return {"week": "", "platforms_played": [], "challenge_done": False}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"week": "", "platforms_played": [], "challenge_done": False}


def save_seasonal(components_dir: str, profile: str, state: Dict[str, Any]) -> None:
    atomic_write_json(seasonal_state_path(components_dir, profile), state)


# --- Fake rarity (deterministic from id) ---


def fake_rarity_percent(aid: str) -> int:
    h = hashlib.sha256(aid.encode("utf-8")).hexdigest()
    v = int(h[:8], 16) % 41 + 5  # 5–45%
    return v


# --- Hall of fame export ---


def build_hall_of_fame_payload(
    profile: str,
    games: List[Dict[str, Any]],
    achievements_unlocked: List[str],
    gamerscore_total: int,
) -> Dict[str, Any]:
    top = sorted(
        games,
        key=lambda g: float(g.get("launcher_playtime_seconds") or 0),
        reverse=True,
    )[:10]
    return {
        "format": "pirate_launcher_hall_of_fame_v1",
        "profile": profile,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gamerscore": gamerscore_total,
        "achievements_count": len(achievements_unlocked),
        "top_games": [
            {"name": g.get("name"), "launcher_playtime_seconds": float(g.get("launcher_playtime_seconds") or 0)}
            for g in top
        ],
    }


# --- Profile card PNG ---


def render_profile_card_png(
    dest_path: str,
    profile_name: str,
    gamerscore: int,
    top_game_names: List[str],
    width: int = 880,
    height: int = 495,
) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    img = Image.new("RGB", (width, height), (18, 18, 22))
    dr = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("segoeui.ttf", 36)
        sub_font = ImageFont.truetype("segoeui.ttf", 22)
        small = ImageFont.truetype("segoeui.ttf", 18)
    except OSError:
        title_font = sub_font = small = ImageFont.load_default()
    dr.text((40, 36), "Pirate Launcher", fill=(200, 200, 210), font=title_font)
    dr.text((40, 100), f"Captain: {profile_name}", fill=(255, 215, 100), font=sub_font)
    dr.text((40, 150), f"Gamerscore: {gamerscore:,} G", fill=(120, 200, 120), font=sub_font)
    y = 220
    dr.text((40, y), "Top games", fill=(150, 150, 160), font=small)
    y += 32
    for i, name in enumerate(top_game_names[:6], 1):
        dr.text((56, y), f"{i}. {name}", fill=(220, 220, 230), font=small)
        y += 28
    dr.text((40, height - 48), "Exported locally — no servers involved.", fill=(100, 100, 110), font=small)
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    img.save(dest_path, "PNG")
    return True


# --- Plugin hooks ---


def run_plugin_hooks(
    event: str,
    plugin_dir: str,
    context: Dict[str, Any],
    log_fn: Optional[Callable[[str], None]] = None,
) -> None:
    if not plugin_dir or not os.path.isdir(plugin_dir):
        return
    for name in sorted(os.listdir(plugin_dir)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(plugin_dir, name)
        mod_name = f"pl_plugin_{name[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn = getattr(mod, f"on_{event}", None)
            if callable(fn):
                fn(context)
        except Exception as e:
            if log_fn:
                log_fn(f"Plugin {name} ({event}): {e}")


# --- Windows idle seconds (optional) ---


def windows_idle_seconds() -> Optional[float]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick = kernel32.GetTickCount()
        idle_ms = tick - lii.dwTime
        return max(0.0, idle_ms / 1000.0)
    except Exception:
        return None


# --- SHA-256 file ---


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --- Extract zip ---


def extract_zip_to(zip_path: str, dest_dir: str, log_fn: Optional[Callable[[str], None]] = None) -> bool:
    try:
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
        if log_fn:
            log_fn(f"Extracted ZIP → {dest_dir}")
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"ZIP extract failed: {e}")
        return False


# --- IGDB (Twitch OAuth + IGDB API) ---


def igdb_fetch_metadata(
    client_id: str,
    client_secret: str,
    game_name: str,
    timeout: int = 20,
) -> Optional[Dict[str, Any]]:
    import urllib.parse
    try:
        import requests
    except ImportError:
        return None
    if not client_id or not client_secret or not game_name:
        return None
    try:
        tr = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=timeout,
        )
        if tr.status_code != 200:
            return None
        token = tr.json().get("access_token")
        if not token:
            return None
        body = f'search "{game_name}"; fields name,first_release_date,genres.name,summary; limit 1;'
        r = requests.post(
            "https://api.igdb.com/v4/games",
            headers={
                "Client-ID": client_id,
                "Authorization": f"Bearer {token}",
            },
            data=body,
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        arr = r.json()
        if isinstance(arr, list) and arr:
            return arr[0]
    except Exception:
        return None
    return None
