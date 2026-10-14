from pathlib import Path
from typing import Optional, Literal
import io
import unicodedata
import re
from PIL import Image

import mutagen
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TALB,
    TRCK,
    TPOS,
    TDRC,
    TCON,
    Encoding,
    ID3NoHeaderError,
    APIC
)
from mutagen.oggvorbis import OggVorbis
from .models import TrackMetadata


def _clean_uconnect_tag(text: Optional[str], fallback: str = "Unknown") -> str:
    """Ensure tag string has no bad accents and is clean for Uconnect 430N/730N indexer."""
    if not text:
        return fallback
    # Transliterate accents: é -> e, ñ -> n
    s = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    # Keep only standard alphanumeric, spaces, and hyphens/punctuation that Uconnect accepts
    s = re.sub(r"[^a-zA-Z0-9 \-.,'()&]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else fallback


def _process_id3_artwork(id3: ID3, action: Literal["strip", "resize_500", "keep"] = "strip"):
    """Handle embedded artwork to prevent Uconnect import from hanging."""
    if action == "strip":
        id3.delall("APIC")
        return

    if action == "resize_500":
        for pic in id3.getall("APIC"):
            try:
                img = Image.open(io.BytesIO(pic.data))
                if img.width > 500 or img.height > 500:
                    img.thumbnail((500, 500), Image.Resampling.LANCZOS)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    pic.data = buf.getvalue()
                    pic.mime = "image/jpeg"
            except Exception:
                # If image is unreadable, strip it to prevent Uconnect import hang
                id3.delall("APIC")
                break


def update_audio_tags(
    target_file: Path,
    meta: TrackMetadata,
    id3_version: str = "2.3",
    artwork_action: Literal["strip", "resize_500", "keep"] = "strip",
    uconnect_mode: bool = True,
) -> bool:
    """
    Safely update or embed tags into the COPIED file in the destination directory.
    Original files are never touched.

    Uconnect requirements:
    - Standard ID3v2.3 (UTF-16) tags
    - Populated Artist (TPE1), Album (TALB), Title (TIT2), Track Number (TRCK)
    - Stripped or resized (<= 500x500) embedded artwork
    """
    ext = target_file.suffix.lower()

    try:
        if ext == ".mp3":
            try:
                id3 = ID3(target_file)
            except ID3NoHeaderError:
                id3 = ID3()

            # Clean metadata values
            if uconnect_mode:
                artist_val = _clean_uconnect_tag(meta.artist, "Unknown Artist")
                album_val = _clean_uconnect_tag(meta.album, "Unknown Album")
                title_val = _clean_uconnect_tag(meta.title, target_file.stem)
            else:
                artist_val = meta.artist or "Unknown Artist"
                album_val = meta.album or "Unknown Album"
                title_val = meta.title or target_file.stem

            track_val = str(meta.track_number) if meta.track_number is not None else "1"

            # Use Encoding.UTF16 (standard for ID3v2.3)
            enc = Encoding.UTF16

            id3.delall("TIT2")
            id3.delall("TPE1")
            id3.delall("TALB")
            id3.delall("TRCK")

            id3.add(TIT2(encoding=enc, text=[title_val]))
            id3.add(TPE1(encoding=enc, text=[artist_val]))
            id3.add(TALB(encoding=enc, text=[album_val]))
            id3.add(TRCK(encoding=Encoding.LATIN1, text=[track_val]))

            if meta.disc_number is not None:
                id3.delall("TPOS")
                id3.add(TPOS(encoding=Encoding.LATIN1, text=[str(meta.disc_number)]))

            if meta.year is not None:
                id3.delall("TDRC")
                id3.delall("TYER")
                # ID3v2.3 uses TYER for year
                id3.add(TDRC(encoding=Encoding.LATIN1, text=[str(meta.year)]))

            if meta.genre:
                genre_val = _clean_uconnect_tag(meta.genre) if uconnect_mode else meta.genre
                id3.delall("TCON")
                id3.add(TCON(encoding=enc, text=[genre_val]))

            # Handle artwork (strip or resize <= 500x500)
            _process_id3_artwork(id3, action=artwork_action)

            # Save strictly as ID3v2.3 with ID3v1 fallback (v1=2)
            id3.save(target_file, v2_version=3, v1=2)
            return True

        elif ext == ".ogg":
            audio = OggVorbis(target_file)
            artist_val = _clean_uconnect_tag(meta.artist) if uconnect_mode else (meta.artist or "Unknown Artist")
            album_val = _clean_uconnect_tag(meta.album) if uconnect_mode else (meta.album or "Unknown Album")
            title_val = _clean_uconnect_tag(meta.title) if uconnect_mode else (meta.title or target_file.stem)

            audio["artist"] = [artist_val]
            audio["album"] = [album_val]
            audio["title"] = [title_val]
            if meta.track_number is not None:
                audio["tracknumber"] = [str(meta.track_number)]

            if artwork_action == "strip":
                if "metadata_block_picture" in audio:
                    del audio["metadata_block_picture"]
                if "coverart" in audio:
                    del audio["coverart"]

            audio.save()
            return True

        elif ext == ".wav":
            # WAV files are left intact to prevent header corruption
            return True

    except Exception as e:
        meta.warnings.append(f"Tag write failed: {str(e)}")
        return False

    return True
