from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class TrackMetadata:
    file_path: Path
    file_size: int = 0
    format: str = ""
    artist: str = ""
    album: str = ""
    title: str = ""
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration_seconds: float = 0.0
    bitrate_kbps: Optional[int] = None
    confidence: str = "low"  # high, medium, low
    detection_source: str = "none"  # tags, path_heuristics, filename, manual
    has_embedded_cover: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_path.name,
            "file_size": self.file_size,
            "format": self.format,
            "artist": self.artist,
            "album": self.album,
            "title": self.title,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "year": self.year,
            "genre": self.genre,
            "duration_seconds": round(self.duration_seconds, 1),
            "bitrate_kbps": self.bitrate_kbps,
            "confidence": self.confidence,
            "detection_source": self.detection_source,
            "has_embedded_cover": self.has_embedded_cover,
            "warnings": self.warnings,
        }
