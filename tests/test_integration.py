import tempfile
import shutil
from pathlib import Path

from src.config import CuratorConfig
from src.scanner import MusicScanner
from src.organizer.planner import OrganizationPlanner
from src.organizer.copier import MusicCopier
from src.organizer.manifest import write_manifests


def test_full_pipeline_mock_files():
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        source_dir = temp_dir / "SourceMusic"
        target_dir = temp_dir / "CleanMusic"

        # Create disorganized source hierarchy
        # e.g. <source>/Classic Rock/Led Zeppelin/1971 - Led Zeppelin IV/01 - Black Dog.mp3
        album_dir = source_dir / "Classic Rock" / "Led Zeppelin" / "1971 - Led Zeppelin IV"
        album_dir.mkdir(parents=True, exist_ok=True)

        track1 = album_dir / "01 - Black Dog.mp3"
        track1.write_bytes(b"MOCK_MP3_DATA_FOR_TESTING")

        track2 = album_dir / "02 - Rock and Roll.ogg"
        track2.write_bytes(b"MOCK_OGG_DATA_FOR_TESTING")

        # Mock artwork file
        art = album_dir / "folder.jpg"
        art.write_bytes(b"MOCK_IMAGE_DATA")

        # Another album with no style folder
        other_dir = source_dir / "Queen" / "A Night at the Opera"
        other_dir.mkdir(parents=True, exist_ok=True)
        track3 = other_dir / "Bohemian Rhapsody.wav"
        track3.write_bytes(b"MOCK_WAV_DATA_FOR_TESTING")

        # 1. Scan
        scanner = MusicScanner(source_dir)
        tracks, art_map = scanner.scan_files()
        assert len(tracks) == 3
        assert len(art_map) == 1

        # 2. Plan
        cfg = CuratorConfig(
            source_dir=source_dir,
            destination_dir=target_dir,
            write_tags_to_destination=False,  # mock audio data has no ID3 headers
            copy_album_art=True,
        )
        planner = OrganizationPlanner(cfg)
        plan = planner.create_plan(tracks)
        assert len(plan) == 3

        # Verify expected target paths
        target_paths = {p.target_path.relative_to(target_dir).as_posix() for p in plan}
        assert "Led Zeppelin/Led Zeppelin IV/01 - Black Dog.mp3" in target_paths
        assert "Led Zeppelin/Led Zeppelin IV/02 - Rock and Roll.ogg" in target_paths
        assert "Queen/A Night at the Opera/Bohemian Rhapsody.wav" in target_paths

        # 3. Copy (non-destructive)
        copier = MusicCopier(cfg)
        completed = copier.execute_plan(plan, album_art_map=art_map)
        assert len(completed) == 3

        # Verify target files exist
        assert (target_dir / "Led Zeppelin" / "Led Zeppelin IV" / "01 - Black Dog.mp3").exists()
        assert (target_dir / "Led Zeppelin" / "Led Zeppelin IV" / "folder.jpg").exists()
        assert (target_dir / "Queen" / "A Night at the Opera" / "Bohemian Rhapsody.wav").exists()

        # Verify originals still exist completely untouched
        assert track1.exists()
        assert track2.exists()
        assert track3.exists()
        assert art.exists()

        # 4. Manifests
        manifests = write_manifests(plan, target_dir)
        assert Path(manifests["json"]).exists()
        assert Path(manifests["csv"]).exists()
