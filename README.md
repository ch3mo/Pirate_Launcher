# Pirate Launcher

**Ad-free, offline-first game launcher** for pirated games, Steam installs, Xbox titles, and more.  
Track real playtime with an optional in-game overlay, import your Steam hours, switch between multiple profiles, and enjoy auto-scraped artwork + metadata — 100% local, zero telemetry, no bloat.

**Latest Release:** [v1.1.0 – Profiles, Playtime Overlay, Steam Sync & UI Overhaul](https://github.com/ch3mo/Pirate_Launcher/releases/latest)

## Features

- **Multi-Profile Support**  
  Create and switch profiles (Main / Kids / Retro / etc.) — each has its own games, playtime, favorites, and settings.

- **Accurate Playtime Tracking**  
  Monitors running processes (psutil) and adds session + total playtime automatically. Persists across restarts.

- **In-Game Overlay** (per-game toggle)  
  Clean, semi-transparent bar at the top: shows current session time, total played, and start time. Safe to disable for anti-cheat games.

- **Steam Playtime Import/Sync**  
  Pull forever playtime from your Steam library via Web API. Incremental sync (only new time) or force full overwrite. Setup dialog included.

- **Auto Metadata & Artwork**  
  Scrapes covers, titles, descriptions, genres, release dates from Steam. Caches images and info locally forever — works 100% offline after first load.

- **Modern UI & Navigation**  
  - Platform filter (All / Steam / Xbox / Pirated) with icons  
  - Search, sort (name / recent / playtime / favorites)  
  - Favorites (★ toggle)  
  - Right-click context menu  
  - Scrolling long titles  
  - Toast notifications for actions  
  - Keyboard shortcuts (Ctrl+F search, Enter launch, Delete remove)

- **Privacy & Control**  
  - Fully local — no accounts, no data sent anywhere  
  - Toggle logging, reset playtime, clear profiles, wipe all data  
  - Choose "Date & Time" or "Time Ago" for recently played column

## Screenshots
**SIGN IN**
<img width="1647" height="834" alt="image" src="https://github.com/user-attachments/assets/7d4e28e9-4f90-4027-814d-fb7f979c92ec" />
**GAME LIBARY**
<img width="1947" height="980" alt="image" src="https://github.com/user-attachments/assets/5b570ec2-1ce4-456b-81c8-42120622fdb2" />
**SETTINGS**
<img width="1949" height="978" alt="image" src="https://github.com/user-attachments/assets/986a1c14-709f-4b68-afe1-deba4e9e1c90" />
**IMPORT STEAM PLAYTIME**

<img width="541" height="461" alt="image" src="https://github.com/user-attachments/assets/1ef972a6-d697-43a0-897a-e750fe28abfe" />

**OVERLAY & NOTIFICATIONS**
<img width="5117" height="1439" alt="image" src="https://github.com/user-attachments/assets/ec28e45a-9e14-4e4e-a660-5969e1f35860" />


## Download & Install

Grab the latest single-file `.exe` from [Releases](https://github.com/ch3mo/Pirate_Launcher/releases):  
→ No Python needed — just run it.

**Latest:** Pirate_Launcher_v1.1.0.exe (recommended)

## Building from Source (optional)

Requirements:  
- Python 3.9+  
- `pip install requests pillow psutil`

Run:  
python pirate_launcher.py

(Or use pyinstaller to bundle your own .exe)

## Roadmap / Known Limitations

- No auto-updater yet  
- Scraping depends on good title matches (manual refresh helps)  
- Large libraries can be slow to load initially  
- No bulk folder import (add .exe one at a time for now)

## Feedback & Contributing

Found a bug? Got a feature idea?  
→ Open an [Issue](https://github.com/ch3mo/Pirate_Launcher/issues)  
→ PRs welcome — especially for UI tweaks, better scraping, or new platforms!

Join the Discord for chat, screenshots, bug reports:  
https://discord.gg/HYsgwK9pje

Thanks for checking it out & enjoy your games! 🏴‍☠️
