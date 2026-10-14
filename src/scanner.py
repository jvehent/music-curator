from pathlib import Path
from typing import List, Generator, Tuple, Optional, Callable, Dict, Set
import os

from .config import SUPPORTED_EXTENSIONS
from .metadata.models import TrackMetadata
from .metadata.reader import read_track_metadata

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class MusicScanner:
    def __init__(self, source_dir: Path):
        self.source_dir = Path(source_dir).resolve()

    def scan_files(
        self,
        progress_cb: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[List[TrackMetadata], Dict[Path, List[Path]]]:
        """
        Scan all audio files and associated artwork in source directory.
        Returns:
            - List of TrackMetadata
            - Dict mapping album directory in source -> list of artwork image files
        """
        audio_paths: List[Path] = []
        album_art_map: Dict[Path, List[Path]] = {}

        if not self.source_dir.exists() or not self.source_dir.is_dir():
            return [], {}

        # First collect all paths
        for root, _, files in os.walk(self.source_dir):
            root_path = Path(root)
            for f in files:
                p = root_path / f
                ext = p.suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    audio_paths.append(p)
                elif ext in IMAGE_EXTENSIONS and any(term in f.lower() for term in ["cover", "folder", "front", "album", "art"]):
                    album_art_map.setdefault(root_path, []).append(p)

        total = len(audio_paths)
        tracks: List[TrackMetadata] = []

        for idx, p in enumerate(audio_paths, 1):
            if progress_cb:
                progress_cb(idx, total, p.name)
            meta = read_track_metadata(p, source_dir=self.source_dir)
            tracks.append(meta)

        return tracks, album_art_map
