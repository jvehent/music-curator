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
    assert resolver.model == "gemini-pro-latest"

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


def test_activity_logs_and_ai_status():
    from fastapi.testclient import TestClient
    from src.ui.server import app, state

    client = TestClient(app)

    # Clear logs initially
    res = client.post("/api/logs/clear")
    assert res.status_code == 200

    # Add a mock log
    state.add_log("ai", "Testing Gemini", "Resolving Funkadelic album", details="Tracks: 10")

    # Fetch logs
    res = client.get("/api/logs")
    assert res.status_code == 200
    data = res.json()
    assert data["total_logs"] >= 1
    latest = data["logs"][-1]
    assert latest["level"] == "ai"
    assert latest["title"] == "Testing Gemini"
    assert latest["message"] == "Resolving Funkadelic album"
    assert "Tracks: 10" in latest["details"]

    # Test since_id filtering
    res_since = client.get(f"/api/logs?since_id={latest['id']}")
    assert res_since.status_code == 200
    assert len(res_since.json()["logs"]) == 0

    # Test AI status endpoint
    res_status = client.get("/api/ai-resolve/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "status" in status_data
    assert "percent" in status_data
    assert "tracks_updated" in status_data

    # Test cancel endpoint
    res_cancel = client.post("/api/ai-resolve/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelling"

