from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal
import re

SUPPORTED_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".wma"}

INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_component(name: str, fallback: str = "Unknown") -> str:
    """Sanitize a single path component (directory or file name) for Windows filesystem."""
    if not name or not name.strip():
        return fallback
    clean = INVALID_WIN_CHARS.sub("_", name)
    clean = re.sub(r"\s+", " ", clean).strip(". ")
    if not clean:
        return fallback
    if clean.upper() in RESERVED_NAMES:
        clean = f"_{clean}"
    return clean[:120]  # keep reasonable length for each component


@dataclass
class CuratorConfig:
    source_dir: Path = field(default_factory=lambda: Path("."))
    destination_dir: Path = field(default_factory=lambda: Path("./organized_music"))
    dry_run: bool = True
    write_tags_to_destination: bool = True
    copy_album_art: bool = True
    conflict_strategy: Literal["suffix", "skip", "overwrite"] = "suffix"
    naming_template: str = "{track:02d} - {title}.{ext}"  # relative to <top>/<artist>/<album>/
    use_online_lookup: bool = False  # MusicBrainz lookup
    clean_title_regex: bool = True  # Strip track numbers/extensions from embedded titles
