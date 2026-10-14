import shutil
import time
from pathlib import Path
from typing import List, Callable, Optional, Dict
from dataclasses import dataclass

from .planner import PlanItem
from ..config import CuratorConfig
from ..metadata.writer import update_audio_tags


@dataclass
class CopyProgress:
    current_index: int = 0
    total_files: int = 0
    current_file: str = ""
    bytes_copied: int = 0
    total_bytes: int = 0
    speed_mb_s: float = 0.0
    status: str = "running"  # running, finished, cancelled, error
    error_message: Optional[str] = None


class MusicCopier:
    def __init__(self, config: CuratorConfig):
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def execute_plan(
        self,
        plan_items: List[PlanItem],
        album_art_map: Optional[Dict[Path, List[Path]]] = None,
        progress_cb: Optional[Callable[[CopyProgress], None]] = None
    ) -> List[PlanItem]:
        """
        Execute the plan non-destructively:
        - Copies audio files from source to destination.
        - Optionally updates tags on the copied file.
        - Optionally copies album artwork to destination album folder.
        - Never alters or moves the original source files.
        """
        self._is_cancelled = False
        total_files = len(plan_items)
        total_bytes = sum(item.track.file_size for item in plan_items)
        bytes_copied = 0
        copied_art_albums = set()

        start_time = time.time()
        completed_items: List[PlanItem] = []

        for idx, item in enumerate(plan_items, 1):
            if self._is_cancelled:
                if progress_cb:
                    progress_cb(CopyProgress(
                        current_index=idx - 1,
                        total_files=total_files,
                        current_file="Cancelled by user",
                        bytes_copied=bytes_copied,
                        total_bytes=total_bytes,
                        status="cancelled",
                    ))
                break

            target_file = item.target_path
            source_file = item.source_path

            # Update progress
            elapsed = max(time.time() - start_time, 0.001)
            speed = (bytes_copied / (1024 * 1024)) / elapsed
            if progress_cb:
                progress_cb(CopyProgress(
                    current_index=idx,
                    total_files=total_files,
                    current_file=f"{item.track.artist} - {item.track.title}",
                    bytes_copied=bytes_copied,
                    total_bytes=total_bytes,
                    speed_mb_s=round(speed, 2),
                    status="running",
                ))

            try:
                # Ensure target directories exist
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Safe non-destructive copy
                shutil.copy2(source_file, target_file)
                bytes_copied += item.track.file_size

                # Optionally write tags to the newly copied destination file
                if self.config.write_tags_to_destination:
                    update_audio_tags(target_file, item.track)

                # Optionally copy album art once per album folder
                if self.config.copy_album_art and album_art_map:
                    source_album_dir = source_file.parent
                    target_album_dir = target_file.parent
                    if source_album_dir in album_art_map and target_album_dir not in copied_art_albums:
                        for art_file in album_art_map[source_album_dir]:
                            target_art = target_album_dir / art_file.name
                            if not target_art.exists():
                                shutil.copy2(art_file, target_art)
                        copied_art_albums.add(target_album_dir)

                item.status = "copied"
                completed_items.append(item)

            except Exception as e:
                item.status = "error"
                item.notes.append(f"Copy failed: {str(e)}")
                completed_items.append(item)

        if not self._is_cancelled and progress_cb:
            progress_cb(CopyProgress(
                current_index=len(completed_items),
                total_files=total_files,
                current_file="Complete",
                bytes_copied=bytes_copied,
                total_bytes=total_bytes,
                speed_mb_s=0.0,
                status="finished",
            ))

        return completed_items
