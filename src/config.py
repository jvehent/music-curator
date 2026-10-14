from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
import unicodedata
import re

SUPPORTED_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".wma"}

INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_uconnect_string(text: str, max_length: int = 32, fallback: str = "Unknown") -> str:
    """
    Sanitize text strictly for Uconnect 430N/730N indexers:
    - Transliterates accented characters (é -> e, ñ -> n, etc.)
    - Removes all characters except standard alphanumeric, spaces, and hyphens
    - Collapses multiple whitespace
    - Enforces max length (default 32 characters)
    """
    if not text or not text.strip():
        return fallback

    # Transliterate accents to plain ASCII
    s = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")

    # Keep only standard alphanumeric, spaces, and hyphens
    s = re.sub(r"[^a-zA-Z0-9 \-]", "", s)

    # Collapse multiple spaces and hyphens
    s = re.sub(r"\s+", " ", s).strip(" -")

    if not s:
        return fallback

    # Check for Windows reserved names
    if s.upper() in RESERVED_NAMES:
        s = f"_{s}"

    # Truncate to max_length, trimming trailing spaces or hyphens
    s = s[:max_length].strip(" -")
    return s if s else fallback


def sanitize_component(
    name: str,
    fallback: str = "Unknown",
    uconnect_mode: bool = True,
    max_length: int = 32
) -> str:
    """Sanitize directory or file name for Windows and Uconnect."""
    if uconnect_mode:
        return sanitize_uconnect_string(name, max_length=max_length, fallback=fallback)

    if not name or not name.strip():
        return fallback

    clean = INVALID_WIN_CHARS.sub("_", name)
    clean = re.sub(r"\s+", " ", clean).strip(". ")
    if not clean:
        return fallback
    if clean.upper() in RESERVED_NAMES:
        clean = f"_{clean}"
    return clean[:max_length]


@dataclass
class CuratorConfig:
    source_dir: Path = field(default_factory=lambda: Path("."))
    destination_dir: Path = field(default_factory=lambda: Path("./organized_music"))
    dry_run: bool = True
    
    # Uconnect 430N / 730N Compatibility Rules
    uconnect_mode: bool = True
    max_component_length: int = 32  # Strict 32 char limit
    max_directory_depth: int = 2     # <Root> / <Artist> / <Album> / <Track>
    id3_version: str = "2.3"         # ID3v2.3 (UTF-16)
    artwork_action: Literal["strip", "resize_500", "keep"] = "strip"  # Prevent import hanging
    
    # Smart AI & Audio Fingerprinting Settings
    gemini_api_key: Optional[str] = None
    acoustid_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"

    write_tags_to_destination: bool = True
    copy_album_art: bool = False     # False for Uconnect to prevent non-audio clutter
    conflict_strategy: Literal["suffix", "skip", "overwrite"] = "suffix"
    use_online_lookup: bool = False
    clean_title_regex: bool = True


CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def load_persistent_config() -> CuratorConfig:
    """Load config from config.json if present, falling back to environment variables."""
    cfg = CuratorConfig()
    cfg.gemini_api_key = os.getenv("GEMINI_API_KEY")
    cfg.acoustid_api_key = os.getenv("ACOUSTID_API_KEY")

    if CONFIG_FILE.exists():
        try:
            import json
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if "gemini_api_key" in data and data["gemini_api_key"]:
                cfg.gemini_api_key = data["gemini_api_key"]
            if "acoustid_api_key" in data and data["acoustid_api_key"]:
                cfg.acoustid_api_key = data["acoustid_api_key"]
            if "artwork_action" in data:
                cfg.artwork_action = data["artwork_action"]
            if "uconnect_mode" in data:
                cfg.uconnect_mode = data["uconnect_mode"]
            if "gemini_model" in data:
                cfg.gemini_model = data["gemini_model"]
        except Exception:
            pass

    return cfg


def save_persistent_config(data: dict):
    """Save persistent user settings to config.json."""
    import json
    current = {}
    if CONFIG_FILE.exists():
        try:
            current = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    current.update(data)
    CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
