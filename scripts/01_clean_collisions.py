"""Step 1 — clean the FLAP export and clip to US + Canada.

    uv run python scripts/01_clean_collisions.py

Reads  data/raw/flap_gbcm_export.csv
Writes data/processed/collisions_clean.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import boundaries, collisions  # noqa: E402

RAW = ROOT / "data/raw/flap_gbcm_export.csv"
OUT = ROOT / "data/processed/collisions_clean.parquet"
BOUNDARY = ROOT / "data/processed/us_ca_boundary.gpkg"


def main() -> int:
    raw = collisions.load_raw(RAW)
    clean, stats = collisions.clean(raw)
    pts = collisions.to_geodataframe(clean)

    boundary = boundaries.fetch(BOUNDARY)
    inside = collisions.clip_to_boundary(pts, boundary)
    stats["dropped_outside_us_canada"] = len(pts) - len(inside)
    stats["final_records"] = len(inside)
    stats["final_birds"] = int(inside["birds"].sum())
    stats["by_country_records"] = inside["country"].value_counts().to_dict()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    inside.to_parquet(OUT)
    (ROOT / "data/processed/clean_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
