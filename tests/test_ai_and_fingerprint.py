from pathlib import Path
from src.metadata.models import TrackMetadata
from src.metadata.ai_resolver import GeminiAlbumResolver
from src.metadata.fingerprint import AcousticFingerprinter


def test_fingerprint_engine_detection():
    fingerprinter = AcousticFingerprinter()
    assert fingerprinter.is_available() is True
    assert fingerprinter.fpcalc_path is not None
    assert "fpcalc" in fingerprinter.fpcalc_path.lower()


def test_ai_resolver_apply_resolution():
    resolver = GeminiAlbumResolver()
    assert resolver.model == "gemini-3.8-flash"

    tracks = [
        TrackMetadata(file_path=Path("01 - UnknownTrack.mp3"), title="UnknownTrack", track_number=None, confidence="low"),
        TrackMetadata(file_path=Path("02 - MysterySong.mp3"), title="MysterySong", track_number=None, confidence="low"),
    ]

    mock_resolution = {
        "success": True,
        "artist": "Incubus",
        "album": "Fungus Amongus",
        "year": 1995,
        "genre": "Funk Metal",
        "tracks": [
            {"filename": "01 - UnknownTrack.mp3", "track_number": 1, "title": "You Will Be a Hot Dancer"},
            {"filename": "02 - MysterySong.mp3", "track_number": 2, "title": "Shaft"},
        ]
    }

    updated = resolver.apply_resolution(tracks, mock_resolution)
    assert updated == 2
    assert tracks[0].artist == "Incubus"
    assert tracks[0].album == "Fungus Amongus"
    assert tracks[0].title == "You Will Be a Hot Dancer"
    assert tracks[0].track_number == 1
    assert tracks[0].year == 1995
    assert tracks[0].confidence == "high"
    assert tracks[0].detection_source == "gemini_ai"

    assert tracks[1].title == "Shaft"
    assert tracks[1].track_number == 2
