# Harmoniq - Music Curator & Library Organizer (Uconnect Edition)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform Windows](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://www.microsoft.com/windows/)
[![Uconnect Compatible](https://img.shields.io/badge/Uconnect-430N%20%2F%20730N-success.svg)](https://www.driveuconnect.com/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Harmoniq** is an intelligent, **strictly non-destructive** music curation and organization tool for Windows, specifically engineered for strict automotive infotainment systems such as **Uconnect 430N / 730N** as well as standard clean library management.

It scans vast, disorganized collections of music files (`.mp3`, `.ogg`, `.wav`), analyzes embedded audio tags and directory hierarchies, corrects and relabels metadata, and safely copies files into an optimized 2-tier structure:

```
<Target Directory>/
  ├── <Artist (<= 32 chars)>/
  │     ├── <Album (<= 32 chars)>/
  │     │     ├── 01 - Track Title.mp3 (<= 32 chars)
  │     │     ├── 02 - Track Title.mp3
  │     │     └── 1-01 - MultiDisc Track.mp3
```

> **Safety Guarantee:** Your original music directory is treated as **strictly read-only**. Files are never moved, renamed, or modified in the source folder.

---

## 🚗 Uconnect 430N / 730N Critical Rules Compliance

Harmoniq strictly enforces the 4 critical Uconnect constraints by default:

1. **Max Directory Depth (Strictly 2 Folders Deep):**
   - Files are organized strictly as `<Target>/<Artist>/<Album>/<Track.mp3>`.
   - Multi-disc albums are kept in the album folder with disc-track numbering (e.g., `1-01 - Title.mp3` or `2-01 - Title.mp3`), completely eliminating 3rd-tier subfolders (`CD1`, `Disc 2`) that cause Uconnect indexers to truncate or skip files.
2. **Standard ID3v2.3 (UTF-16) Tags:**
   - Every file has verified, populated `Artist (TPE1)`, `Album (TALB)`, `Track Title (TIT2)`, and `Track Number (TRCK)`.
   - Tags are saved strictly in **ID3v2.3** with UTF-16 encoding (along with ID3v1 fallback), preventing garbled characters or tracks falling back to "Unknown Artist".
3. **Strict 32-Character ASCII Naming:**
   - Folder and file names are kept **under 32 characters**.
   - Accented characters are automatically transliterated (`é` → `e`, `ñ` → `n`, `ö` → `o`, etc.).
   - Special characters (`/ \ : * ? " < > | '`) are eliminated, adhering to standard alphanumeric characters, spaces, and hyphens.
4. **Stripping / Resizing Embedded Artwork:**
   - Strips oversized embedded album art (or downscales to ≤ 500×500 px) to prevent MP3 header bloat that causes Uconnect import freezes, allowing the vehicle's internal Gracenote database to match art seamlessly.

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
python -m src.cli scan "G:\My Drive\Music\Albums\Funk"
```

#### Simulate reorganization (Dry Run):
```powershell
python -m src.cli organize "G:\My Drive\Music\Albums\Funk" "D:\UconnectMusic" --dry-run
```

#### Execute non-destructive copy with artwork stripping:
```powershell
python -m src.cli organize "G:\My Drive\Music\Albums\Funk" "D:\UconnectMusic" --artwork-action strip
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
│   ├── config.py               # Uconnect rules, path sanitization, and configuration
│   ├── scanner.py              # Recursive audio scanner
│   ├── cli.py                  # Rich command-line interface with Uconnect flags
│   ├── metadata/
│   │   ├── models.py           # TrackMetadata dataclasses
│   │   ├── reader.py           # Mutagen reader (MP3, OGG, WAV, etc.)
│   │   ├── writer.py           # Strict ID3v2.3 writer & artwork processor
│   │   ├── heuristics.py       # Path and filename heuristics
│   │   └── musicbrainz.py      # Online MusicBrainz lookup client
│   ├── organizer/
│   │   ├── planner.py          # Collision detection, 2-tier depth, & 32-char planner
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
    ├── test_integration.py
    └── test_uconnect.py
```

---

## 🧪 Running Tests

```powershell
python -m pytest tests/
```

---

## 🐙 Publishing to GitHub

```powershell
git remote add origin https://github.com/<your-username>/music-curator.git
git branch -M main
git push -u origin main
```
