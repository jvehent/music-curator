import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import acoustid

from .models import TrackMetadata

logger = logging.getLogger(__name__)

# Search for fpcalc in PATH or common Windows winget installation locations
def _find_fpcalc() -> Optional[str]:
    found = shutil.which("fpcalc")
    if found:
        return found

    # Check winget user package directory
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for p in winget_pkgs.rglob("fpcalc.exe"):
                return str(p)

    return None


# Initialize acoustid with fpcalc path
_fpcalc_path = _find_fpcalc()
if _fpcalc_path:
    acoustid.FPCALC = _fpcalc_path


class AcousticFingerprinter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ACOUSTID_API_KEY")
        self.fpcalc_path = _find_fpcalc()
        if self.fpcalc_path:
            acoustid.FPCALC = self.fpcalc_path

    def is_available(self) -> bool:
        return self.fpcalc_path is not None

    def fingerprint_audio(self, file_path: Path) -> Tuple[Optional[float], Optional[bytes], Optional[str]]:
        """Calculate the acoustic fingerprint of an audio file."""
        if not self.is_available():
            return None, None, "fpcalc (Chromaprint) executable not found."

        try:
            duration, fp = acoustid.fingerprint_file(str(file_path))
            return duration, fp, None
        except Exception as e:
            return None, None, f"Fingerprinting failed: {str(e)}"

    def identify_track(self, file_path: Path, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate acoustic fingerprint and match against the AcoustID / MusicBrainz database.
        """
        key = api_key or self.api_key
        duration, fp, err = self.fingerprint_audio(file_path)

        if err or not fp:
            return {
                "success": False,
                "error": err or "Failed to generate fingerprint.",
            }

        fp_str = fp.decode("utf-8", errors="ignore") if isinstance(fp, bytes) else str(fp)

        if not key:
            return {
                "success": False,
                "has_fingerprint": True,
                "duration_seconds": duration,
                "fingerprint_preview": fp_str[:40] + "...",
                "error": "AcoustID API key is required for live audio matching. Get a free key at https://acoustid.org/api-key",
            }

        try:
            results = acoustid.lookup(key, fp, duration, meta=["recordings", "releasegroups", "compress"])
            matches = []

            for result in results.get("results", []):
                score = result.get("score", 0)
                for rec in result.get("recordings", []):
                    title = rec.get("title")
                    artist = ""
                    artists = rec.get("artists", [])
                    if artists:
                        artist = artists[0].get("name", "")

                    album = ""
                    release_groups = rec.get("releasegroups", [])
                    if release_groups:
                        album = release_groups[0].get("title", "")

                    matches.append({
                        "score": round(score, 2),
                        "recording_id": rec.get("id"),
                        "title": title,
                        "artist": artist,
                        "album": album,
                    })

            # Sort by score descending
            matches.sort(key=lambda x: x["score"], reverse=True)

            if matches:
                top = matches[0]
                return {
                    "success": True,
                    "matched": True,
                    "top_match": top,
                    "all_matches": matches[:5],
                    "fingerprint": fp_str[:40] + "...",
                }

            return {
                "success": True,
                "matched": False,
                "message": "No match found in AcoustID database.",
                "fingerprint": fp_str[:40] + "...",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"AcoustID query error: {str(e)}",
            }
