import logging
from typing import Optional, Dict, Any, List
import musicbrainzngs

logger = logging.getLogger(__name__)

# Setup useragent per MusicBrainz API requirements
musicbrainzngs.set_useragent("HarmoniqMusicCurator", "1.0.0", "https://github.com/music-curator")


def search_release(artist: str, album: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search MusicBrainz for release/album matches."""
    if not artist or not album or artist.lower() == "unknown artist":
        return []

    try:
        query = f'artist:"{artist}" AND release:"{album}"'
        result = musicbrainzngs.search_releases(query=query, limit=limit)
        releases = result.get("release-list", [])
        matches = []
        for r in releases:
            match_info = {
                "id": r.get("id"),
                "title": r.get("title"),
                "artist": r.get("artist-credit-phrase"),
                "date": r.get("date"),
                "country": r.get("country"),
                "track_count": r.get("medium-track-count"),
                "status": r.get("status"),
            }
            matches.append(match_info)
        return matches
    except Exception as e:
        logger.warning(f"MusicBrainz search error: {e}")
        return []


def search_recording(artist: str, title: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search MusicBrainz for track/recording matches."""
    if not title:
        return []

    try:
        query = f'recording:"{title}"'
        if artist and artist.lower() != "unknown artist":
            query += f' AND artist:"{artist}"'
        result = musicbrainzngs.search_recordings(query=query, limit=limit)
        recordings = result.get("recording-list", [])
        matches = []
        for rec in recordings:
            release_title = ""
            releases = rec.get("release-list", [])
            if releases:
                release_title = releases[0].get("title", "")
            matches.append({
                "id": rec.get("id"),
                "title": rec.get("title"),
                "artist": rec.get("artist-credit-phrase"),
                "album": release_title,
                "length": rec.get("length"),
            })
        return matches
    except Exception as e:
        logger.warning(f"MusicBrainz recording search error: {e}")
        return []
