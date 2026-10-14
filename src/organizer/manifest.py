import csv
import json
from pathlib import Path
from typing import List
from .planner import PlanItem


def write_manifests(plan_items: List[PlanItem], output_dir: Path) -> dict:
    """Write audit manifest in both JSON and CSV formats."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "organization_manifest.json"
    csv_path = output_dir / "organization_manifest.csv"

    # Write JSON
    records = [item.to_dict() for item in plan_items]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # Write CSV
    if records:
        fieldnames = [
            "status",
            "source_path",
            "target_path",
            "artist",
            "album",
            "title",
            "track_number",
            "disc_number",
            "year",
            "genre",
            "format",
            "confidence",
            "detection_source",
            "notes"
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                row = dict(r)
                row["notes"] = "; ".join(row.get("notes", []))
                writer.writerow(row)

    return {
        "json": str(json_path),
        "csv": str(csv_path),
    }
