import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# Common genres / styles to help disambiguate depth
KNOWN_STYLES = {
    "rock", "pop", "jazz", "classical", "metal", "blues", "hip-hop", "hip hop",
    "rap", "electronic", "dance", "ambient", "folk", "country", "reggae",
    "punk", "soundtrack", "ost", "r&b", "soul", "funk", "disco", "indie",
    "alternative", "latin", "world", "house", "techno", "trance", "synthwave",
    "prog rock", "heavy metal", "hard rock", "edm", "lo-fi", "lofi", "acoustic"
}

YEAR_PATTERN = re.compile(r"[\(\[]?(19\d{2}|20\d{2})[\)\]]?")
DISC_PATTERN = re.compile(r"^(?:cd|disc|disk)\s*([0-9]{1,2})$", re.IGNORECASE)

FILENAME_TRACK_PATTERNS = [
    # 01 - Artist - Title
    re.compile(r"^(?P<track>\d{1,3})\s*[-_.]\s*(?P<artist>[^-]+?)\s*[-_]\s*(?P<title>.+)$"),
    # 01 - Title or 01. Title or 01_Title
    re.compile(r"^(?P<track>\d{1,3})\s*[-_.]\s*(?P<title>.+)$"),
    # 01 Title (with space)
    re.compile(r"^(?P<track>\d{1,3})\s+(?P<title>[^\d].+)$"),
    # Artist - Title
    re.compile(r"^(?P<artist>[^-]+?)\s*[-_]\s*(?P<title>.+)$"),
]


def clean_string(val: Optional[str]) -> str:
    if not val:
        return ""
    # replace underscores with spaces
    s = val.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_filename(stem: str) -> Dict[str, Any]:
    """Parse track number, artist, and title from filename stem."""
    stem = stem.strip()
    res: Dict[str, Any] = {
        "track_number": None,
        "artist": "",
        "title": stem,
    }

    for pattern in FILENAME_TRACK_PATTERNS:
        m = pattern.match(stem)
        if m:
            groups = m.groupdict()
            if "track" in groups:
                try:
                    res["track_number"] = int(groups["track"])
                except ValueError:
                    pass
            if "artist" in groups and groups["artist"]:
                res["artist"] = clean_string(groups["artist"])
            if "title" in groups and groups["title"]:
                res["title"] = clean_string(groups["title"])
            break

    return res


def extract_year_from_album(raw_album: str) -> Tuple[str, Optional[int]]:
    """Extract (clean_album_name, year) if album contains year like (1994) or 1994 - Album."""
    year: Optional[int] = None
    clean_album = raw_album

    # Check for prefix: "1973 - The Dark Side of the Moon"
    prefix_match = re.match(r"^(\d{4})\s*[-_]\s*(.+)$", raw_album)
    if prefix_match:
        try:
            year = int(prefix_match.group(1))
            clean_album = prefix_match.group(2)
        except ValueError:
            pass
    else:
        # Check for year in parentheses: "The Dark Side of the Moon (1973)"
        ym = YEAR_PATTERN.search(raw_album)
        if ym:
            try:
                year = int(ym.group(1))
                clean_album = YEAR_PATTERN.sub("", raw_album).strip()
            except ValueError:
                pass

    clean_album = re.sub(r"\s+", " ", clean_album).strip(" -_[]()")
    return clean_album, year


def parse_path_hierarchy(file_path: Path, source_dir: Path) -> Dict[str, Any]:
    """
    Decompose relative path components into Style / Artist / Album / Track.
    Handles:
      - <Style>/<Artist>/<Album>/<Track>
      - <Artist>/<Album>/<Track>
      - <Artist>/<Album>/Disc 1/<Track>
      - <Style>/<Artist>/<Album>/Disc 1/<Track>
    """
    info: Dict[str, Any] = {
        "style": "",
        "artist": "",
        "album": "",
        "disc_number": None,
        "year": None,
        "track_number": None,
        "title": file_path.stem,
        "confidence": "low",
    }

    try:
        rel = file_path.relative_to(source_dir)
        parts = list(rel.parts)
    except Exception:
        parts = [file_path.name]

    if not parts:
        return info

    filename = parts[-1]
    folders = parts[:-1]
    stem = Path(filename).stem

    # Extract disc number if the deepest folder is CD 1 / Disc 2
    if folders:
        disc_match = DISC_PATTERN.match(folders[-1].strip())
        if disc_match:
            try:
                info["disc_number"] = int(disc_match.group(1))
            except ValueError:
                pass
            folders = folders[:-1]

    # Now inspect remaining folders
    num_folders = len(folders)

    if num_folders >= 3:
        # Check if folder 0 is a known style or just a style folder
        f0_lower = folders[0].lower().strip()
        info["style"] = clean_string(folders[0])
        info["artist"] = clean_string(folders[1])
        raw_album = clean_string(folders[2])
        clean_album, year = extract_year_from_album(raw_album)
        info["album"] = clean_album
        info["year"] = year
        info["confidence"] = "medium"
    elif num_folders == 2:
        # Could be <Artist>/<Album> or <Style>/<Artist>
        # If folder 0 is a known style, maybe artist is folder 1 and album is in filename
        if folders[0].lower().strip() in KNOWN_STYLES:
            info["style"] = clean_string(folders[0])
            info["artist"] = clean_string(folders[1])
            info["album"] = "Singles & Unknown Album"
        else:
            info["artist"] = clean_string(folders[0])
            raw_album = clean_string(folders[1])
            clean_album, year = extract_year_from_album(raw_album)
            info["album"] = clean_album
            info["year"] = year
        info["confidence"] = "medium"
    elif num_folders == 1:
        # Single folder: could be "Artist - Album" or just "Artist"
        folder = folders[0]
        if " - " in folder:
            split_parts = folder.split(" - ", 1)
            info["artist"] = clean_string(split_parts[0])
            clean_album, year = extract_year_from_album(clean_string(split_parts[1]))
            info["album"] = clean_album
            info["year"] = year
        else:
            info["artist"] = clean_string(folder)
            info["album"] = "Unknown Album"
        info["confidence"] = "low"

    # Merge filename parsing
    file_parsed = parse_filename(stem)
    if file_parsed.get("track_number") is not None:
        info["track_number"] = file_parsed["track_number"]
    if file_parsed.get("title"):
        info["title"] = file_parsed["title"]
    if not info["artist"] and file_parsed.get("artist"):
        info["artist"] = file_parsed["artist"]

    return info
