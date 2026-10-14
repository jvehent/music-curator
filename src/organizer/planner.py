from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from ..config import sanitize_component, CuratorConfig
from ..metadata.models import TrackMetadata


@dataclass
class PlanItem:
    track: TrackMetadata
    source_path: Path
    target_path: Path
    target_artist_dir: str
    target_album_dir: str
    target_filename: str
    has_conflict: bool = False
    conflict_resolved: bool = False
    status: str = "ready"  # ready, warning, conflict
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "source_filename": self.source_path.name,
            "target_path": str(self.target_path),
            "target_artist": self.target_artist_dir,
            "target_album": self.target_album_dir,
            "target_filename": self.target_filename,
            "artist": self.track.artist,
            "album": self.track.album,
            "title": self.track.title,
            "track_number": self.track.track_number,
            "disc_number": self.track.disc_number,
            "year": self.track.year,
            "genre": self.track.genre,
            "format": self.track.format,
            "confidence": self.track.confidence,
            "detection_source": self.track.detection_source,
            "has_conflict": self.has_conflict,
            "status": self.status,
            "notes": self.notes,
        }


class OrganizationPlanner:
    def __init__(self, config: CuratorConfig):
        self.config = config

    def build_filename(self, track: TrackMetadata) -> str:
        ext = track.format.lower().lstrip(".")
        title = sanitize_component(track.title or track.file_path.stem, "Unknown Title")

        # Format track number
        if track.disc_number and track.disc_number > 1 and track.track_number is not None:
            prefix = f"{track.disc_number}-{track.track_number:02d}"
        elif track.track_number is not None:
            prefix = f"{track.track_number:02d}"
        else:
            prefix = ""

        if prefix:
            raw_name = f"{prefix} - {title}.{ext}"
        else:
            raw_name = f"{title}.{ext}"

        return sanitize_component(raw_name, fallback=f"track.{ext}")

    def create_plan(self, tracks: List[TrackMetadata]) -> List[PlanItem]:
        plan_items: List[PlanItem] = []
        target_dest = Path(self.config.destination_dir).resolve()

        # Track used target paths to detect collisions
        allocated_paths: Dict[Path, int] = {}

        for track in tracks:
            artist_clean = sanitize_component(track.artist, fallback="Unknown Artist")
            album_clean = sanitize_component(track.album, fallback="Unknown Album")
            filename_clean = self.build_filename(track)

            planned_target = target_dest / artist_clean / album_clean / filename_clean

            has_conflict = False
            notes = list(track.warnings)

            # Check if this destination is already allocated in the current plan
            if planned_target in allocated_paths:
                has_conflict = True
                allocated_paths[planned_target] += 1
                count = allocated_paths[planned_target]

                if self.config.conflict_strategy == "suffix":
                    stem = Path(filename_clean).stem
                    ext = Path(filename_clean).suffix
                    resolved_filename = f"{stem} ({count}){ext}"
                    planned_target = target_dest / artist_clean / album_clean / resolved_filename
                    notes.append(f"Name collision resolved by appending suffix ({count})")
                else:
                    notes.append("Target path collision detected")
            else:
                allocated_paths[planned_target] = 0

            status = "ready"
            if track.confidence == "low" or "Unknown" in artist_clean:
                status = "warning"
            if has_conflict and self.config.conflict_strategy != "suffix":
                status = "conflict"

            item = PlanItem(
                track=track,
                source_path=track.file_path,
                target_path=planned_target,
                target_artist_dir=artist_clean,
                target_album_dir=album_clean,
                target_filename=planned_target.name,
                has_conflict=has_conflict,
                conflict_resolved=(has_conflict and self.config.conflict_strategy == "suffix"),
                status=status,
                notes=notes,
            )
            plan_items.append(item)

        return plan_items
