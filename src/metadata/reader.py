from pathlib import Path
from typing import Optional, Dict, Any
import mutagen
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis

from .models import TrackMetadata
from .heuristics import parse_path_hierarchy, clean_string


def _extract_tag_value(tags: Any, keys: list) -> str:
    """Safely get string value for any of the given tag keys."""
    if not tags:
        return ""
    for k in keys:
        if k in tags:
            val = tags[k]
            if isinstance(val, (list, tuple)) and len(val) > 0:
                s = str(val[0]).strip()
                if s:
                    return s
            elif hasattr(val, "text") and len(val.text) > 0:
                s = str(val.text[0]).strip()
                if s:
                    return s
            elif val:
                s = str(val).strip()
                if s:
                    return s
    return ""


def _parse_track_number(raw_val: str) -> Optional[int]:
    """Parse track number from strings like '5', '05/12', '5/12'."""
    if not raw_val:
        return None
    val = str(raw_val).split("/")[0].strip()
    try:
        return int(val)
    except ValueError:
        return None


def _parse_year(raw_val: str) -> Optional[int]:
    """Parse year from strings like '1997', '1997-05-12'."""
    if not raw_val:
        return None
    val = str(raw_val).strip()[:4]
    try:
        return int(val)
    except ValueError:
        return None


def read_track_metadata(file_path: Path, source_dir: Optional[Path] = None) -> TrackMetadata:
    """
    Read metadata from audio file using Mutagen tags with fallback to directory/file heuristics.
    """
    ext = file_path.suffix.lower()
    meta = TrackMetadata(
        file_path=file_path,
        file_size=file_path.stat().st_size if file_path.exists() else 0,
        format=ext,
    )

    tags = None
    audio = None
    has_cover = False

    try:
        audio = mutagen.File(file_path)
        if audio is not None:
            tags = audio.tags
            if hasattr(audio, "info") and audio.info:
                meta.duration_seconds = getattr(audio.info, "length", 0.0)
                meta.bitrate_kbps = int(getattr(audio.info, "bitrate", 0) / 1000) if getattr(audio.info, "bitrate", 0) else None

            # Check cover art
            if ext == ".mp3" and tags:
                for key in tags.keys():
                    if key.startswith("APIC"):
                        has_cover = True
                        break
            elif ext == ".ogg" and tags:
                if "metadata_block_picture" in tags or "coverart" in tags:
                    has_cover = True
    except Exception as e:
        meta.warnings.append(f"Tag read error: {str(e)}")

    # Extract tags
    raw_artist = ""
    raw_album = ""
    raw_title = ""
    raw_track = ""
    raw_disc = ""
    raw_year = ""
    raw_genre = ""

    if tags is not None:
        raw_artist = _extract_tag_value(tags, ["TPE1", "TPE2", "artist", "ARTIST", "Author", "performer"])
        raw_album = _extract_tag_value(tags, ["TALB", "album", "ALBUM", "WM/AlbumTitle"])
        raw_title = _extract_tag_value(tags, ["TIT2", "title", "TITLE", "Title", "WM/Title"])
        raw_track = _extract_tag_value(tags, ["TRCK", "tracknumber", "TRACKNUMBER", "WM/TrackNumber"])
        raw_disc = _extract_tag_value(tags, ["TPOS", "discnumber", "DISCNUMBER"])
        raw_year = _extract_tag_value(tags, ["TDRC", "TYER", "date", "DATE", "year", "YEAR", "WM/Year"])
        raw_genre = _extract_tag_value(tags, ["TCON", "genre", "GENRE", "WM/Genre"])

    meta.has_embedded_cover = has_cover
    meta.artist = clean_string(raw_artist)
    meta.album = clean_string(raw_album)
    meta.title = clean_string(raw_title)
    meta.track_number = _parse_track_number(raw_track)
    meta.disc_number = _parse_track_number(raw_disc)
    meta.year = _parse_year(raw_year)
    meta.genre = clean_string(raw_genre)

    # Check quality of extracted tags
    has_good_tags = bool(meta.artist and meta.title and meta.artist.lower() not in {"unknown", "unknown artist"})

    if has_good_tags:
        meta.confidence = "high"
        meta.detection_source = "tags"
        if not meta.album:
            meta.album = "Unknown Album"
    else:
        # Fallback to heuristics
        if source_dir:
            h = parse_path_hierarchy(file_path, source_dir)
            if not meta.artist and h.get("artist"):
                meta.artist = h["artist"]
            if (not meta.album or meta.album == "Unknown Album") and h.get("album"):
                meta.album = h["album"]
            if not meta.title and h.get("title"):
                meta.title = h["title"]
            if meta.track_number is None and h.get("track_number") is not None:
                meta.track_number = h["track_number"]
            if meta.disc_number is None and h.get("disc_number") is not None:
                meta.disc_number = h["disc_number"]
            if meta.year is None and h.get("year") is not None:
                meta.year = h["year"]
            if not meta.genre and h.get("style"):
                meta.genre = h["style"]

            meta.confidence = h.get("confidence", "low")
            meta.detection_source = "path_heuristics"
        else:
            meta.confidence = "low"
            meta.detection_source = "filename"

    # Final safety fallbacks
    if not meta.title:
        meta.title = clean_string(file_path.stem)
    if not meta.artist:
        meta.artist = "Unknown Artist"
        meta.warnings.append("Could not identify artist")
    if not meta.album:
        meta.album = "Unknown Album"
        meta.warnings.append("Could not identify album")

    return meta
