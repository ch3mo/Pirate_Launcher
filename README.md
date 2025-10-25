# Pirate Launcher

Pirate Launcher is a simple, user-friendly desktop application for managing and launching your games, including pirated, Steam, Xbox, and Microsoft Store titles. It automatically scrapes game art and descriptions from RAWG and Steam API, providing a clean interface with alphabetical sorting and platform badges.

## Features
- Manual addition of games by selecting `.exe` files from specific directories ( (Pirated, Steam, Xbox).
- Automatic scraping of game art and descriptions (cached for offline use).
- Alphabetical sorting of games with platform indicators (Steam, Xbox, Pirated).
- Light/dark theme toggle.
- Multi-profile support for organizing games.
- Launch, remove, and refresh games easily.
- Instant boot with no delays, even offline.

<img width="1397" height="607" alt="image" src="https://github.com/user-attachments/assets/0fb4f3ec-5329-4386-8202-4afca8b568ed" />

## Prerequisites
- **Python 3.8+**: Download from [python.org](https://www.python.org/downloads/).
- **Libraries**: `requests` and `pillow` (installed via pip).
- **No internet required after initial scrape** (art and info are cached locally).

## Installation
Choose your preferred method:

### Option 1: Pre-built EXE (Recommended - No Python Needed)
1. **Download the Latest Release**:
   - Visit [GitHub Releases](https://github.com/ch3mo/Pirate_Launcher/releases/tag/Base) (always use the latest release if possible).
   - Download the `.exe` file from the assets section.

2. **Run the Launcher**:
   - Double-click the `.exe` file to launch.
   - No installation required — runs directly.

### Option 2: Source Code (For Developers)
1. **Clone the Repository**:
    git clone https://github.com/yourusername/pirate-launcher.git
    cd pirate-launcher

2. **Install Dependencies**:
    pip install requests pillow

## Setup
1. **Run the Launcher**:
- Create a batch file (e.g., `start.bat`) in the same directory:
    @echo off
    pythonw pirate_launcher.py

- Double-click `start.bat` to launch (no command window).

2. **Initial Setup**:
- On first run, create an account or sign in.
- Add games using the "Add Game" dropdown, selecting from Pirated, Steam, or Xbox directories.
- Art and descriptions will be scraped and cached automatically.

## Instructions / Usage
1. **Adding a Game**:
- Click "Add Game" dropdown.
- Choose source (Pirated, Steam, Xbox).
- Browse and select the game's `.exe` file.
- Enter the game name (auto-suggested from folder).
- Art and description are scraped and shown instantly.

2. **Launching a Game**:
- Select a game from the list.
- Click "Launch" to run it.

3. **Removing a Game**:
- Select a game.
- Click "Remove".

4. **Refreshing List**:
- Click "Refresh" to update the game list.

5. **Theme Toggle**:
- Go to Settings > Toggle Theme.

6. **Profiles**:
- Settings > Profiles > Create/Switch/Delete.

7. **Clear Data**:
- Settings > Clear Games or Clear All Data.

## FAQ
- **Why is there a delay on first add?**  
The launcher scrapes art and description from online APIs. Once cached, it's instant and works offline.

- **No art or description for a game?**  
Try renaming the game to match the exact title on RAWG or Steam. If it persists, the game may not be indexed yet.

- **Game not launching?**  
Ensure the `.exe` path is correct. Some games may require additional dependencies or admin rights.

- **How to add Microsoft Store games?**  
Use "Pirated Games" option and navigate to `C:\Program Files\WindowsApps` (may require admin access).

- **Can I add custom platforms?**  
Currently supports Pirated, Steam, Xbox. For others, use "Pirated Games" option.

- **Is this secure?**  
Yes, no data is shared. All scraping is local; no personal info stored.

- **How to get help?**  
Join our Discord for support, updates, and community: https://discord.gg/HYsgwK9pje

## Contributing
Fork the repo, make changes, and submit a pull request. Suggestions for new features (e.g., more platforms, search bar) are welcome!

## License
MIT License - feel free to use and modify.
