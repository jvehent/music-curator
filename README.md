# Harmoniq - Music Curator & Library Organizer

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform Windows](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://www.microsoft.com/windows/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Harmoniq** is an intelligent, **strictly non-destructive** music curation and organization tool for Windows. It scans vast, disorganized collections of music files (`.mp3`, `.ogg`, `.wav`, `.flac`, `.m4a`), analyzes embedded audio tags and folder hierarchies, fills in missing metadata through path heuristics or MusicBrainz, and safely copies the files into a clean structure:

```
<Target Directory>/
  ├── <Artist>/
  │     ├── <Album>/
  │     │     ├── 01 - Track Title.mp3
  │     │     ├── 02 - Track Title.ogg
  │     │     ├── 03 - Track Title.wav
  │     │     └── folder.jpg (album art preserved)
```

> **Safety Guarantee:** Your original music directory is treated as **strictly read-only**. Files are never moved, renamed, or modified in the source folder.

---

## ✨ Features

- 🛡️ **Non-Destructive Copy Engine:** Copies files to a new destination without ever altering or touching the source files.
- 🏷️ **Multi-Tier Metadata Detection:**
  - **Tier 1:** Native tag extraction (`ID3v2.3`, `ID3v2.4`, `ID3v1` for MP3; Vorbis comments for OGG; RIFF/WAVE chunks for WAV; FLAC/M4A).
  - **Tier 2:** Smart path heuristics detecting `<Style>/<Artist>/<Album>/...` or `<Artist>/<Album>/...`, disc folders (`CD 1`, `Disc 2`), and release years (e.g. `1973 - Dark Side` or `Abbey Road (1969)`).
  - **Tier 3:** Intelligent filename parsing (e.g. `01 - Title`, `01. Title`, `Artist - Title`).
  - **Tier 4:** Integrated **MusicBrainz API** lookup for automatic online verification.
- 🖥️ **State-of-the-Art Windows Interface:**
  - Glassmorphic dark-mode dashboard.
  - Interactive reorganization diff table showing original path vs. proposed target path.
  - Built-in audio snippet player to preview tracks directly in the app.
  - Inline metadata editor for quick corrections.
  - Real-time copy progress with transfer speed (MB/s), file counters, and cancel control.
- 🪟 **Windows Native Resilience:**
  - Automatically sanitizes invalid Windows characters (`\ / : * ? " < > |`).
  - Guards against reserved Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
  - Prevents path collision with automatic numeric suffixing (e.g., `Song (1).mp3`).
- 📊 **Audit Manifests:**
  - Generates detailed `organization_manifest.json` and `organization_manifest.csv` (compatible with Excel) in the destination folder.
- ⌨️ **Command-Line Interface:** Powerful CLI with rich terminal tables and progress bars for automated batch workflows.

---

## 🚀 Quick Start on Windows

### 1. Launch with Web Interface (Recommended)

Simply double-click:
```cmd
run.bat
```
Or run from PowerShell / Terminal:
```powershell
python main.py
```
This automatically launches the server and opens your browser at `http://localhost:8765`.

### 2. Launch with Command-Line Interface (CLI)

#### Scan a source folder:
```powershell
python -m src.cli scan "C:\Users\julie\Music\Disorganized"
```

#### Simulate reorganization (Dry Run):
```powershell
python -m src.cli organize "C:\Users\julie\Music\Disorganized" "C:\Users\julie\Music\Clean" --dry-run
```

#### Execute non-destructive copy:
```powershell
python -m src.cli organize "C:\Users\julie\Music\Disorganized" "C:\Users\julie\Music\Clean"
```

---

## 🛠️ Project Structure

```
music-curator/
├── main.py                     # Entry point (launches UI & opens browser)
├── run.bat                     # Windows Explorer double-click launcher
├── run.ps1                     # PowerShell launcher script
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── src/
│   ├── config.py               # Path sanitization and app configuration
│   ├── scanner.py              # Recursive audio and artwork scanner
│   ├── cli.py                  # Rich command-line interface
│   ├── metadata/
│   │   ├── models.py           # TrackMetadata dataclasses
│   │   ├── reader.py           # Mutagen reader (MP3, OGG, WAV, etc.)
│   │   ├── writer.py           # Tag writer for destination files
│   │   ├── heuristics.py       # Path and filename heuristics
│   │   └── musicbrainz.py      # Online MusicBrainz lookup client
│   ├── organizer/
│   │   ├── planner.py          # Collision detection & target path planner
│   │   ├── copier.py           # Safe non-destructive copy engine
│   │   └── manifest.py         # JSON and CSV audit log generator
│   └── ui/
│       ├── server.py           # FastAPI local server & streaming endpoints
│       └── static/             # Glassmorphic frontend assets
│           ├── index.html
│           ├── style.css
│           └── app.js
└── tests/
    ├── test_heuristics.py
    ├── test_planner.py
    └── test_integration.py
```

---

## 🧪 Running Tests

```powershell
python -m pytest tests/
```

---

## 🐙 Publishing to GitHub

To push this repository to your personal GitHub account:

1. Create a new repository on [GitHub](https://github.com/new) (e.g. named `music-curator`).
2. Add the remote and push:
```powershell
git remote add origin https://github.com/<your-username>/music-curator.git
git branch -M main
git push -u origin main
```
