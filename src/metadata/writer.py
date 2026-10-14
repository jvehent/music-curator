from pathlib import Path
from typing import Optional
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.oggvorbis import OggVorbis
from .models import TrackMetadata


def update_audio_tags(target_file: Path, meta: TrackMetadata) -> bool:
    """
    Safely update or embed tags into the COPIED file in the destination directory.
    Original files are never touched.
    """
    ext = target_file.suffix.lower()

    try:
        if ext == ".mp3":
            try:
                audio = EasyID3(target_file)
            except ID3NoHeaderError:
                audio = mutagen.File(target_file, easy=True)
                audio.add_tags()

            if meta.artist:
                audio["artist"] = meta.artist
            if meta.album:
                audio["album"] = meta.album
            if meta.title:
                audio["title"] = meta.title
            if meta.track_number is not None:
                audio["tracknumber"] = str(meta.track_number)
            if meta.disc_number is not None:
                audio["discnumber"] = str(meta.disc_number)
            if meta.year is not None:
                audio["date"] = str(meta.year)
            if meta.genre:
                audio["genre"] = meta.genre
            audio.save()
            return True

        elif ext == ".ogg":
            audio = OggVorbis(target_file)
            if meta.artist:
                audio["artist"] = [meta.artist]
            if meta.album:
                audio["album"] = [meta.album]
            if meta.title:
                audio["title"] = [meta.title]
            if meta.track_number is not None:
                audio["tracknumber"] = [str(meta.track_number)]
            if meta.disc_number is not None:
                audio["discnumber"] = [str(meta.disc_number)]
            if meta.year is not None:
                audio["date"] = [str(meta.year)]
            if meta.genre:
                audio["genre"] = [meta.genre]
            audio.save()
            return True

        # WAV files can have ID3 or RIFF INFO chunks, but often best left intact unless mutagen supports WAVE ID3
        elif ext == ".wav":
            try:
                from mutagen.wave import WAVE
                audio = WAVE(target_file)
                # WAVE in mutagen doesn't have easy id3 mapping out of the box, safe to skip or log
                return True
            except Exception:
                return False

    except Exception as e:
        meta.warnings.append(f"Tag write failed: {str(e)}")
        return False

    return True
