"""Step 2 — fetch Overture building footprints around collision sites.

    uv run python scripts/02_fetch_buildings.py [--workers 8]

Reads  data/processed/collisions_clean.parquet
Writes data/cache/buildings/<cell>.parquet (one per ~2 km grid cell; resumable)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402
from overturemaps import core  # noqa: E402

from pipeline import buildings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pad-m", type=float, default=250.0)
    args = ap.parse_args()

    pts = gpd.read_parquet(ROOT / "data/processed/collisions_clean.parquet")
    release = core.get_latest_release()
    (ROOT / "data/cache").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/cache/OVERTURE_RELEASE").write_text(release)
    print(f"Overture release {release}", flush=True)
    t0 = time.time()
    buildings.fetch_near_points(pts, ROOT / "data/cache/buildings", pad_m=args.pad_m,
                                workers=args.workers, release=release)
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
