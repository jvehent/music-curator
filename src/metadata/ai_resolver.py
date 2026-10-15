import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from .models import TrackMetadata

logger = logging.getLogger(__name__)


class GeminiAlbumResolver:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro-latest"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # Ensure clean model name
        self.model = model.replace("models/", "") if model else "gemini-pro-latest"
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")

    def is_configured(self) -> bool:
        return self.client is not None

    def resolve_album_context(
        self,
        folder_name: str,
        tracks: List[TrackMetadata],
        relative_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use Gemini LLM to analyze the entire album directory context and resolve:
        - Canonical Artist Name
        - Official Album Title
        - Release Year & Genre
        - Correct Track Number & Clean Track Title for every file
        """
        if not self.client:
            return {
                "success": False,
                "error": "Gemini API key is not configured. Please set GEMINI_API_KEY or configure it in Settings.",
            }

        # Build track listing summary for LLM prompt
        track_summaries = []
        for t in tracks:
            item = {
                "filename": t.file_path.name,
                "duration_seconds": round(t.duration_seconds, 1) if t.duration_seconds else None,
                "existing_title": t.title,
                "existing_artist": t.artist if t.artist != "Unknown Artist" else None,
                "existing_track_num": t.track_number,
            }
            track_summaries.append(item)

        prompt = f"""You are an expert music archivist and discographer.
Analyze the following disorganized album directory and infer the canonical album metadata and exact tracklist.

Directory Name: {folder_name}
Relative Path: {relative_path or folder_name}
Files in Folder ({len(tracks)} tracks):
{json.dumps(track_summaries, indent=2)}

Instructions:
1. Identify the official Artist name and official Album title.
2. Determine the original release Year and primary Genre.
3. For each file, identify its official Track Number (1, 2, 3...) and official Track Title.
4. If this is a Various Artists compilation or soundtrack, set artist to "Various Artists" and set each track's individual artist if recognizable.
5. Return ONLY a valid JSON object matching this schema:
{{
  "artist": "Official Artist Name",
  "album": "Official Album Title",
  "year": 1995,
  "genre": "Rock",
  "confidence": "high",
  "reasoning": "Brief explanation of how the album was identified",
  "tracks": [
    {{
      "filename": "original_filename.mp3",
      "track_number": 1,
      "title": "Clean Track Title",
      "artist": "Optional Track Artist (if different from album artist)"
    }}
  ]
}}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )

            response_text = response.text.strip()

            # Extract JSON block if wrapped in markdown ```json ... ```
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response_text

            data = json.loads(json_str)
            data["success"] = True
            return data

        except Exception as e:
            logger.error(f"Gemini API album resolution error: {e}")
            return {
                "success": False,
                "error": f"AI Resolution failed: {str(e)}",
            }

    def apply_resolution(self, tracks: List[TrackMetadata], resolution: Dict[str, Any]) -> int:
        """Apply the AI-inferred metadata back into the TrackMetadata objects."""
        if not resolution.get("success"):
            return 0

        artist = resolution.get("artist")
        album = resolution.get("album")
        year = resolution.get("year")
        genre = resolution.get("genre")

        tracks_by_filename = {t.file_path.name: t for t in tracks}
        updated_count = 0

        for item in resolution.get("tracks", []):
            fname = item.get("filename")
            t = tracks_by_filename.get(fname)
            if t:
                if artist:
                    t.artist = item.get("artist") or artist
                if album:
                    t.album = album
                if item.get("title"):
                    t.title = item.get("title")
                if item.get("track_number") is not None:
                    t.track_number = item.get("track_number")
                if year and not t.year:
                    t.year = year
                if genre and not t.genre:
                    t.genre = genre

                t.confidence = "high"
                t.detection_source = "gemini_ai"
                updated_count += 1

        return updated_count
