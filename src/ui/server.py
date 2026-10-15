import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from ..config import CuratorConfig, load_persistent_config, save_persistent_config
from ..scanner import MusicScanner
from ..organizer.planner import OrganizationPlanner, PlanItem
from ..organizer.copier import MusicCopier, CopyProgress
from ..organizer.manifest import write_manifests
from ..metadata.musicbrainz import search_release, search_recording
from ..metadata.models import TrackMetadata
from ..metadata.ai_resolver import GeminiAlbumResolver
from ..metadata.fingerprint import AcousticFingerprinter

app = FastAPI(title="Harmoniq - Music Curator & Organizer")

# Global session state
class SessionState:
    def __init__(self):
        self.config: CuratorConfig = load_persistent_config()
        self.source_dir: Optional[Path] = self.config.source_dir if self.config.source_dir != Path(".") else None
        self.destination_dir: Optional[Path] = self.config.destination_dir if self.config.destination_dir != Path("./organized_music") else None
        self.tracks: List[TrackMetadata] = []
        self.art_map: Dict[Path, List[Path]] = {}
        self.plan: List[PlanItem] = []
        self.copier: Optional[MusicCopier] = None
        self.copy_progress: CopyProgress = CopyProgress(status="idle")
        self.ai_resolver: GeminiAlbumResolver = GeminiAlbumResolver(
            api_key=self.config.gemini_api_key,
            model=self.config.gemini_model or "gemini-pro-latest"
        )
        self.fingerprinter: AcousticFingerprinter = AcousticFingerprinter(api_key=self.config.acoustid_api_key)
        self.lock = threading.Lock()

        # Real-time Activity Logs & AI Progress State
        self.activity_logs: List[Dict[str, Any]] = []
        self.log_counter: int = 0
        self.ai_cancel_requested: bool = False
        self.ai_progress: Dict[str, Any] = {
            "status": "idle",
            "current_folder": "",
            "current_index": 0,
            "total_folders": 0,
            "percent": 0,
            "tracks_updated": 0,
            "message": "Ready",
            "resolutions": [],
            "error": None
        }

    def add_log(self, level: str, title: str, message: str, details: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            self.log_counter += 1
            item = {
                "id": self.log_counter,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": level,  # "info", "ai", "success", "warning", "error"
                "title": title,
                "message": message,
                "details": details
            }
            self.activity_logs.append(item)
            if len(self.activity_logs) > 500:
                self.activity_logs.pop(0)
            return item

state = SessionState()


class ScanRequest(BaseModel):
    source_dir: str


class PlanRequest(BaseModel):
    destination_dir: str
    conflict_strategy: str = "suffix"
    write_tags: bool = True
    copy_art: bool = False
    uconnect_mode: bool = True
    artwork_action: str = "strip"  # strip, resize_500, keep


class UpdateTrackRequest(BaseModel):
    index: int
    artist: Optional[str] = None
    album: Optional[str] = None
    title: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None


class MBSearchRequest(BaseModel):
    artist: str
    album: Optional[str] = ""
    title: Optional[str] = ""


@app.post("/api/scan")
def api_scan(req: ScanRequest):
    src = Path(req.source_dir).resolve()
    if not src.exists() or not src.is_dir():
        state.add_log("error", "Scan Failed", f"Source directory does not exist: {req.source_dir}")
        raise HTTPException(status_code=400, detail="Source directory does not exist or is not a folder.")

    state.add_log("info", "Scan Started", f"Scanning audio library: {src}")
    scanner = MusicScanner(src)
    tracks, art_map = scanner.scan_files()

    with state.lock:
        state.source_dir = src
        state.tracks = tracks
        state.art_map = art_map
        state.plan = []
        save_persistent_config({"source_dir": str(src)})

    # Calculate statistics
    formats: Dict[str, int] = {}
    confidence: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    total_size = 0

    for t in tracks:
        formats[t.format] = formats.get(t.format, 0) + 1
        confidence[t.confidence] = confidence.get(t.confidence, 0) + 1
        total_size += t.file_size

    fmt_str = ", ".join(f"{k.upper()}: {v}" for k, v in formats.items()) or "None"
    state.add_log(
        "success",
        "Scan Complete",
        f"Discovered {len(tracks)} audio tracks ({total_size / (1024*1024):.1f} MB) across {len(art_map)} artwork folders. Confidence: {confidence['high']} High, {confidence['medium'] + confidence['low']} Inferred/Warnings.",
        details=f"Formats: {fmt_str}\nTotal Size: {total_size} bytes\nArtwork Folders: {len(art_map)}"
    )

    return {
        "status": "success",
        "total_tracks": len(tracks),
        "total_size_bytes": total_size,
        "artwork_folders_found": len(art_map),
        "formats": formats,
        "confidence": confidence,
        "sample_tracks": [t.to_dict() for t in tracks[:100]],
    }


@app.post("/api/plan")
def api_plan(req: PlanRequest):
    with state.lock:
        if not state.tracks:
            state.add_log("warning", "Plan Failed", "No tracks available to plan. Please scan a source directory first.")
            raise HTTPException(status_code=400, detail="No tracks scanned yet. Please scan a source directory first.")

        dest = Path(req.destination_dir).resolve()
        state.destination_dir = dest
        state.config.destination_dir = dest
        state.config.conflict_strategy = req.conflict_strategy
        state.config.write_tags_to_destination = req.write_tags
        state.config.copy_album_art = req.copy_art
        state.config.uconnect_mode = req.uconnect_mode
        state.config.artwork_action = req.artwork_action

        planner = OrganizationPlanner(state.config)
        state.plan = planner.create_plan(state.tracks)

        save_persistent_config({
            "destination_dir": str(dest),
            "artwork_action": req.artwork_action,
            "write_tags": req.write_tags,
            "copy_art": req.copy_art,
            "uconnect_mode": req.uconnect_mode,
        })

        ready_count = sum(1 for p in state.plan if p.status == "ready")
        warning_count = sum(1 for p in state.plan if p.status == "warning")
        conflict_count = sum(1 for p in state.plan if p.status == "conflict")

        summary = {
            "total_items": len(state.plan),
            "ready_count": ready_count,
            "warning_count": warning_count,
            "conflict_count": conflict_count,
            "items": [p.to_dict() for p in state.plan],
        }

    state.add_log(
        "success",
        "Plan Ready",
        f"Generated organization plan: {len(state.plan)} tracks mapped ({ready_count} ready, {warning_count} warnings, {conflict_count} conflicts).",
        details=f"Target: {dest}\nUconnect Mode: {req.uconnect_mode}\nArtwork Action: {req.artwork_action}\nWrite Tags: {req.write_tags}"
    )

    return summary


@app.post("/api/update-track")
def api_update_track(req: UpdateTrackRequest):
    with state.lock:
        if req.index < 0 or req.index >= len(state.tracks):
            raise HTTPException(status_code=400, detail="Track index out of range.")

        t = state.tracks[req.index]
        if req.artist is not None:
            t.artist = req.artist.strip()
        if req.album is not None:
            t.album = req.album.strip()
        if req.title is not None:
            t.title = req.title.strip()
        if req.track_number is not None:
            t.track_number = req.track_number
        if req.disc_number is not None:
            t.disc_number = req.disc_number
        if req.year is not None:
            t.year = req.year
        if req.genre is not None:
            t.genre = req.genre.strip()

        t.confidence = "high"
        t.detection_source = "manual"

        state.add_log("info", "Track Edited", f"Track #{req.index + 1} updated manually: '{t.artist} - {t.title}' ({t.album}).")

        # Recompute plan if destination set
        if state.destination_dir:
            planner = OrganizationPlanner(state.config)
            state.plan = planner.create_plan(state.tracks)
            return {"status": "updated", "plan_item": state.plan[req.index].to_dict()}

        return {"status": "updated", "track": t.to_dict()}


@app.post("/api/search-musicbrainz")
def api_search_mb(req: MBSearchRequest):
    if req.album:
        results = search_release(req.artist, req.album)
    else:
        results = search_recording(req.artist, req.title)
    return {"results": results}


class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    acoustid_api_key: Optional[str] = None
    gemini_model: Optional[str] = "gemini-pro-latest"
    artwork_action: Optional[str] = None
    uconnect_mode: Optional[bool] = None
    write_tags: Optional[bool] = None
    copy_art: Optional[bool] = None
    source_dir: Optional[str] = None
    destination_dir: Optional[str] = None


class AIResolveRequest(BaseModel):
    album_name: Optional[str] = None
    track_indices: Optional[List[int]] = None


class FingerprintRequest(BaseModel):
    index: int


RECOMMENDED_MODELS = [
    {"id": "gemini-pro-latest", "name": "gemini-pro-latest (Default - Most Powerful & Intelligent)"},
    {"id": "gemini-3.8-flash", "name": "gemini-3.8-flash (Latest Flash - Ultra Fast)"},
    {"id": "gemini-flash-latest", "name": "gemini-flash-latest (Auto-updated Latest Flash)"},
    {"id": "gemini-3.7-flash", "name": "gemini-3.7-flash"},
    {"id": "gemini-3.5-flash", "name": "gemini-3.5-flash"},
]


@app.get("/api/settings")
def api_get_settings():
    with state.lock:
        return {
            "has_gemini_key": bool(state.config.gemini_api_key),
            "gemini_api_key": state.config.gemini_api_key or "",
            "gemini_key_preview": f"{state.config.gemini_api_key[:6]}...{state.config.gemini_api_key[-4:]}" if state.config.gemini_api_key else "",
            "has_acoustid_key": bool(state.config.acoustid_api_key),
            "acoustid_api_key": state.config.acoustid_api_key or "",
            "acoustid_key_preview": f"{state.config.acoustid_api_key[:4]}...{state.config.acoustid_api_key[-3:]}" if state.config.acoustid_api_key else "",
            "has_fpcalc": state.fingerprinter.is_available(),
            "gemini_model": state.config.gemini_model or "gemini-pro-latest",
            "available_models": RECOMMENDED_MODELS,
            "uconnect_mode": state.config.uconnect_mode,
            "artwork_action": state.config.artwork_action,
            "write_tags": state.config.write_tags_to_destination,
            "copy_art": state.config.copy_album_art,
            "source_dir": str(state.source_dir) if state.source_dir else (str(state.config.source_dir) if state.config.source_dir != Path(".") else ""),
            "destination_dir": str(state.destination_dir) if state.destination_dir else (str(state.config.destination_dir) if state.config.destination_dir != Path("./organized_music") else ""),
        }


@app.post("/api/settings")
def api_update_settings(req: SettingsRequest):
    with state.lock:
        updates = {}
        if req.gemini_model is not None:
            clean_m = req.gemini_model.replace("models/", "").strip()
            state.config.gemini_model = clean_m or "gemini-pro-latest"
            updates["gemini_model"] = state.config.gemini_model

        if req.gemini_api_key is not None:
            state.config.gemini_api_key = req.gemini_api_key.strip() or None
            updates["gemini_api_key"] = state.config.gemini_api_key

        if req.acoustid_api_key is not None:
            state.config.acoustid_api_key = req.acoustid_api_key.strip() or None
            updates["acoustid_api_key"] = state.config.acoustid_api_key
            state.fingerprinter = AcousticFingerprinter(api_key=state.config.acoustid_api_key)

        if req.artwork_action is not None:
            state.config.artwork_action = req.artwork_action
            updates["artwork_action"] = req.artwork_action

        if req.uconnect_mode is not None:
            state.config.uconnect_mode = req.uconnect_mode
            updates["uconnect_mode"] = req.uconnect_mode

        if req.write_tags is not None:
            state.config.write_tags_to_destination = req.write_tags
            updates["write_tags"] = req.write_tags

        if req.copy_art is not None:
            state.config.copy_album_art = req.copy_art
            updates["copy_art"] = req.copy_art

        if req.source_dir is not None:
            p = req.source_dir.strip()
            if p:
                state.source_dir = Path(p).resolve()
                updates["source_dir"] = str(state.source_dir)

        if req.destination_dir is not None:
            p = req.destination_dir.strip()
            if p:
                state.destination_dir = Path(p).resolve()
                updates["destination_dir"] = str(state.destination_dir)

        # Re-initialize resolver with latest key and model
        state.ai_resolver = GeminiAlbumResolver(
            api_key=state.config.gemini_api_key,
            model=state.config.gemini_model or "gemini-pro-latest"
        )

        save_persistent_config(updates)
        state.add_log("info", "Settings Updated", f"Configuration updated: model={state.config.gemini_model}, uconnect={state.config.uconnect_mode}, artwork={state.config.artwork_action}.")
        return {"status": "saved", "config": updates}


def _run_ai_resolve_worker(groups: Dict[str, List[TrackMetadata]], source_dir: Optional[Path]):
    with state.lock:
        state.ai_cancel_requested = False
        total_folders = len(groups)
        state.ai_progress = {
            "status": "running",
            "current_folder": "Initializing...",
            "current_index": 0,
            "total_folders": total_folders,
            "percent": 0,
            "tracks_updated": 0,
            "message": f"Starting AI analysis across {total_folders} folder(s)...",
            "resolutions": [],
            "error": None
        }

    state.add_log(
        "ai",
        "AI Resolution Started",
        f"Processing {total_folders} album folder(s) using Gemini ({state.config.gemini_model})."
    )

    total_updated = 0
    resolutions = []

    for idx, (folder_name, folder_tracks) in enumerate(groups.items(), 1):
        with state.lock:
            if state.ai_cancel_requested:
                state.ai_progress["status"] = "cancelled"
                state.ai_progress["message"] = "AI Resolution cancelled by user."
                state.add_log("warning", "AI Cancelled", "AI resolution stopped by user.")
                break

            state.ai_progress["current_folder"] = folder_name
            state.ai_progress["current_index"] = idx
            state.ai_progress["percent"] = int(((idx - 1) / total_folders) * 100)
            state.ai_progress["message"] = f"Querying Gemini for '{folder_name}' ({len(folder_tracks)} tracks)..."

        state.add_log(
            "ai",
            f"Querying Gemini [{idx}/{total_folders}]",
            f"Analyzing folder '{folder_name}' ({len(folder_tracks)} tracks) with model {state.config.gemini_model}..."
        )

        rel = ""
        if source_dir:
            try:
                rel = str(folder_tracks[0].file_path.parent.relative_to(source_dir))
            except Exception:
                pass

        try:
            res = state.ai_resolver.resolve_album_context(
                folder_name=folder_name,
                tracks=folder_tracks,
                relative_path=rel
            )
        except Exception as e:
            res = {"success": False, "error": str(e)}

        with state.lock:
            if res.get("success"):
                updated = state.ai_resolver.apply_resolution(folder_tracks, res)
                total_updated += updated
                artist = res.get("artist") or "Unknown Artist"
                album = res.get("album") or "Unknown Album"
                year = res.get("year")
                genre = res.get("genre")
                reasoning = res.get("reasoning")

                res_summary = {
                    "folder": folder_name,
                    "artist": artist,
                    "album": album,
                    "year": year,
                    "genre": genre,
                    "tracks_updated": updated,
                    "reasoning": reasoning
                }
                resolutions.append(res_summary)
                state.ai_progress["resolutions"].append(res_summary)
                state.ai_progress["tracks_updated"] = total_updated

                details_text = f"Artist: {artist}\nAlbum: {album}\nYear: {year or 'N/A'}\nGenre: {genre or 'N/A'}\nTracks Updated: {updated}"
                if reasoning:
                    details_text += f"\nReasoning: {reasoning}"

                state.add_log(
                    "success",
                    f"Resolved: {artist} - {album}",
                    f"Identified {updated} tracks in '{folder_name}' (Year: {year or 'N/A'}, Genre: {genre or 'N/A'}).",
                    details=details_text
                )
            else:
                err = res.get("error", "Unknown error")
                if "402" in err or "RESOURCE_EXHAUSTED" in err:
                    state.add_log(
                        "error",
                        f"Quota Exhausted: '{folder_name}'",
                        "Gemini API returned 402 RESOURCE_EXHAUSTED. Please verify your Google AI Studio project billing or try another model in Settings.",
                        details=err
                    )
                else:
                    state.add_log(
                        "warning",
                        f"Unresolved: '{folder_name}'",
                        f"AI could not identify metadata: {err}",
                        details=err
                    )

            state.ai_progress["percent"] = int((idx / total_folders) * 100)

    with state.lock:
        if state.ai_progress["status"] != "cancelled":
            state.ai_progress["status"] = "completed"
            state.ai_progress["percent"] = 100
            state.ai_progress["tracks_updated"] = total_updated
            state.ai_progress["message"] = f"Complete: {total_updated} track(s) updated across {len(resolutions)} album(s)."

        # Recompute plan if destination is set
        if state.destination_dir and total_updated > 0:
            planner = OrganizationPlanner(state.config)
            state.plan = planner.create_plan(state.tracks)
            state.add_log("info", "Plan Recomputed", f"Organization plan updated with {total_updated} newly canonicalized tracks.")

    state.add_log(
        "success",
        "AI Resolution Completed",
        f"Batch AI resolution completed. Total {total_updated} track(s) updated across {len(resolutions)} album(s)."
    )


@app.post("/api/ai-resolve")
def api_ai_resolve(req: AIResolveRequest):
    with state.lock:
        if not state.tracks:
            raise HTTPException(status_code=400, detail="No tracks scanned yet.")
        if not state.ai_resolver.is_configured():
            raise HTTPException(status_code=400, detail="Gemini API Key is not configured. Please enter your API key in Settings.")
        if state.ai_progress.get("status") == "running":
            raise HTTPException(status_code=400, detail="AI resolution is already in progress.")

        # Determine tracks to resolve
        if req.track_indices:
            target_tracks = [state.tracks[i] for i in req.track_indices if 0 <= i < len(state.tracks)]
        elif req.album_name:
            target_tracks = [t for t in state.tracks if t.album == req.album_name]
        else:
            # Default to all tracks with low/medium confidence or Unknown
            target_tracks = [t for t in state.tracks if t.confidence in {"low", "medium"} or "Unknown" in t.artist or "Unknown" in t.album]

        if not target_tracks:
            state.add_log("info", "AI Check", "No unknown or low-confidence tracks required AI resolution.")
            return {"status": "no_tracks", "message": "No matching tracks need AI resolution."}

        # Group by parent directory
        groups: Dict[str, List[TrackMetadata]] = {}
        for t in target_tracks:
            groups.setdefault(t.file_path.parent.name, []).append(t)

        src_dir = state.source_dir

    t = threading.Thread(target=_run_ai_resolve_worker, args=(groups, src_dir), daemon=True)
    t.start()

    return {
        "status": "started",
        "total_folders": len(groups),
        "total_tracks": len(target_tracks)
    }


@app.get("/api/ai-resolve/status")
def api_ai_resolve_status():
    with state.lock:
        prog = dict(state.ai_progress)
        if prog.get("status") == "completed" and state.plan:
            prog["plan"] = [p.to_dict() for p in state.plan]
        return prog


@app.post("/api/ai-resolve/cancel")
def api_ai_resolve_cancel():
    with state.lock:
        state.ai_cancel_requested = True
    return {"status": "cancelling"}


@app.post("/api/fingerprint-track")
def api_fingerprint_track(req: FingerprintRequest):
    with state.lock:
        if req.index < 0 or req.index >= len(state.tracks):
            raise HTTPException(status_code=400, detail="Invalid track index.")

        track = state.tracks[req.index]
        state.add_log("info", "Acoustic Fingerprint", f"Generating audio fingerprint for track #{req.index + 1}: '{track.file_path.name}'...")

        result = state.fingerprinter.identify_track(track.file_path)

        if result.get("matched") and result.get("top_match"):
            top = result["top_match"]
            state.add_log(
                "success",
                "Fingerprint Match",
                f"AcoustID matched track #{req.index + 1}: '{top.get('artist')} - {top.get('title')}' (Score: {int(top.get('score', 0)*100)}%).",
                details=f"Artist: {top.get('artist')}\nTitle: {top.get('title')}\nAlbum: {top.get('album')}\nScore: {top.get('score')}"
            )
            return {
                "status": "matched",
                "track_index": req.index,
                "suggested": {
                    "artist": top.get("artist"),
                    "title": top.get("title"),
                    "album": top.get("album"),
                    "score": top.get("score"),
                },
                "details": result,
            }

        state.add_log("warning", "Fingerprint Result", f"AcoustID: {result.get('error') or 'No match found in AcoustID database.'}")
        return {"status": "result", "track_index": req.index, "details": result}


def _run_copy_worker():
    with state.lock:
        plan_copy = list(state.plan)
        art_map_copy = dict(state.art_map)
        copier = MusicCopier(state.config)
        state.copier = copier

    def progress_callback(prog: CopyProgress):
        with state.lock:
            state.copy_progress = prog

    copier.execute_plan(plan_copy, album_art_map=art_map_copy, progress_cb=progress_callback)

    # Write manifests on finish
    if state.destination_dir:
        write_manifests(plan_copy, state.destination_dir)
        state.add_log("success", "Copy Finished", f"Successfully copied files to '{state.destination_dir}'. Audit manifests saved.")


@app.post("/api/execute")
def api_execute():
    with state.lock:
        if not state.plan:
            raise HTTPException(status_code=400, detail="No plan generated. Click 'Generate Plan' first.")
        if state.copy_progress.status == "running":
            raise HTTPException(status_code=400, detail="Copy operation is already running.")

        state.copy_progress = CopyProgress(
            current_index=0,
            total_files=len(state.plan),
            current_file="Preparing copy...",
            bytes_copied=0,
            total_bytes=sum(item.track.file_size for item in state.plan),
            status="running"
        )
        state.add_log("info", "Copy Started", f"Starting non-destructive copy of {len(state.plan)} files to '{state.destination_dir}'...")

    t = threading.Thread(target=_run_copy_worker, daemon=True)
    t.start()
    return {"status": "started"}


@app.get("/api/progress")
def api_progress():
    with state.lock:
        p = state.copy_progress
        return {
            "current_index": p.current_index,
            "total_files": p.total_files,
            "current_file": p.current_file,
            "bytes_copied": p.bytes_copied,
            "total_bytes": p.total_bytes,
            "speed_mb_s": p.speed_mb_s,
            "status": p.status,
            "error_message": p.error_message,
        }


@app.post("/api/cancel")
def api_cancel():
    with state.lock:
        if state.copier:
            state.copier.cancel()
        state.copy_progress.status = "cancelled"
    state.add_log("warning", "Copy Cancelled", "Copy operation cancelled by user.")
    return {"status": "cancelling"}


@app.get("/api/logs")
def api_get_logs(since_id: int = Query(0)):
    with state.lock:
        new_logs = [log for log in state.activity_logs if log["id"] > since_id]
        return {
            "logs": new_logs,
            "total_logs": len(state.activity_logs),
            "latest_id": state.log_counter,
            "ai_status": state.ai_progress.get("status", "idle"),
            "copy_status": state.copy_progress.status,
        }


@app.post("/api/logs/clear")
def api_clear_logs():
    with state.lock:
        state.activity_logs.clear()
    return {"status": "cleared"}


@app.get("/api/audio-stream")
def api_audio_stream(path: str = Query(...)):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")

    ext = p.suffix.lower()
    media_types = {
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(p, media_type=media_type, headers={"Accept-Ranges": "bytes"})


@app.get("/api/open-folder")
def api_open_folder(path: str = Query(...)):
    """Open a folder in Windows Explorer."""
    p = Path(path)
    if p.exists():
        os.startfile(str(p))
        return {"status": "opened"}
    return {"status": "not_found"}


# Mount static assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def read_root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Harmoniq Music Curator API is running."}


def start_server(port: int = 8765):
    print(f"\n=======================================================")
    print(f"🎵 Harmoniq Music Curator is running at:")
    print(f"   http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
