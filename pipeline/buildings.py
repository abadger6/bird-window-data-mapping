"""Overture building footprints near collision sites.

Adapted from bird-window-collision-modeling/pipeline/buildings.py (geometry
cleaning + height backfill), with the risk-model geometry terms removed and a
point-driven fetch added so we only pull footprints where collisions were
actually reported.

Height sources, in order of preference (recorded in ``height_source``):
    1. ``overture``  — Overture ``height`` (LiDAR / OSM / ML-derived)
    2. ``floors``    — Overture ``num_floors`` × 3 m
    3. ``assumed``   — no height in Overture; extruded at DEFAULT_ASSUMED_HEIGHT_M
                        so the footprint is still visible. Flagged in the UI.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

DEFAULT_FLOOR_HEIGHT_M = 3.0
DEFAULT_MIN_AREA_M2 = 20.0
DEFAULT_MIN_HEIGHT_M = 2.0
DEFAULT_MAX_HEIGHT_M = 600.0
DEFAULT_ASSUMED_HEIGHT_M = 6.0

# North America Albers Equal Area — one metric CRS for the whole US + Canada
# extent. Distance distortion is a few percent at most, which is immaterial
# at the 25 m snap scale.
PROJECTED_CRS = "ESRI:102008"

KEEP_COLS = ["id", "name", "height", "num_floors", "class", "subtype", "geometry"]


# --------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------

def fetch_cells(points: gpd.GeoDataFrame, cell_deg: float, pad_m: float) -> list[tuple[str, tuple]]:
    """Group points into a ``cell_deg`` grid; return (cell_key, padded bbox) per cell."""
    cx = np.floor(points["lon"].to_numpy() / cell_deg).astype(int)
    cy = np.floor(points["lat"].to_numpy() / cell_deg).astype(int)
    df = pd.DataFrame({"cx": cx, "cy": cy, "lon": points["lon"].to_numpy(), "lat": points["lat"].to_numpy()})
    out = []
    for (x, y), g in df.groupby(["cx", "cy"]):
        lat0 = g["lat"].mean()
        dlat = pad_m / 111_320
        dlon = pad_m / (111_320 * max(math.cos(math.radians(lat0)), 0.1))
        bbox = (g["lon"].min() - dlon, g["lat"].min() - dlat, g["lon"].max() + dlon, g["lat"].max() + dlat)
        out.append((f"{x}_{y}", tuple(round(v, 6) for v in bbox)))
    return out


def _fetch_one(key: str, bbox: tuple, cache_dir: Path, release: str | None) -> tuple[str, int]:
    path = cache_dir / f"{key}.parquet"
    if path.exists():
        return key, -1
    import overturemaps

    g = overturemaps.geodataframe("building", bbox=bbox, release=release)
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    if len(g):
        g["name"] = g["names"].map(lambda n: (n or {}).get("primary") if isinstance(n, dict) else None)
    else:
        g["name"] = pd.Series(dtype="object")
    for c in KEEP_COLS:
        if c not in g.columns:
            g[c] = None
    g[KEEP_COLS].to_parquet(path)
    return key, len(g)


def fetch_near_points(points: gpd.GeoDataFrame, cache_dir: str | Path, *, cell_deg: float = 0.02,
                      pad_m: float = 250.0, workers: int = 8, release: str | None = None) -> None:
    """Fetch Overture buildings for every grid cell containing collision points.

    Each cell is cached as its own parquet, so the run is resumable.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cells = fetch_cells(points, cell_deg, pad_m)
    todo = [(k, b) for k, b in cells if not (cache_dir / f"{k}.parquet").exists()]
    print(f"{len(cells)} cells, {len(cells) - len(todo)} cached, {len(todo)} to fetch", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_fetch_one, k, b, cache_dir, release): k for k, b in todo}
        for f in as_completed(futs):
            done += 1
            try:
                key, n = f.result()
                if done % 50 == 0 or done == len(todo):
                    print(f"  {done}/{len(todo)} (last {key}: {n} bldgs)", flush=True)
            except Exception as e:  # keep going; rerun picks up failures
                print(f"  FAILED {futs[f]}: {e}", flush=True)


def _fetch_parts_one(key: str, bbox: tuple, cache_dir: Path, release: str | None) -> None:
    path = cache_dir / f"{key}.parquet"
    if path.exists():
        return
    import overturemaps

    g = overturemaps.geodataframe("building_part", bbox=bbox, release=release)
    cols = ["building_id", "height", "num_floors"]
    df = pd.DataFrame({c: g[c] if c in g.columns else pd.Series(dtype="float64") for c in cols})
    df.to_parquet(path)


def fetch_parts(bldgs: gpd.GeoDataFrame, cache_dir: str | Path, *, cell_deg: float = 0.02,
                workers: int = 10, release: str | None = None) -> pd.DataFrame:
    """Fetch Overture ``building_part`` rows covering ``bldgs`` (EPSG:4326).

    Parts are queried per grid cell using the tight bbox of the buildings in
    that cell; results are cached per cell. Returns building_id/height/num_floors.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    b = bldgs.geometry.bounds
    cx = np.floor(b["minx"] / cell_deg).astype(int)
    cy = np.floor(b["miny"] / cell_deg).astype(int)
    jobs = []
    for (x, y), g in b.groupby([cx, cy]):
        bbox = (g.minx.min(), g.miny.min(), g.maxx.max(), g.maxy.max())
        jobs.append((f"{x}_{y}", tuple(round(v, 6) for v in bbox)))
    todo = [j for j in jobs if not (cache_dir / f"{j[0]}.parquet").exists()]
    print(f"building parts: {len(jobs)} cells, {len(todo)} to fetch", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_fetch_parts_one, k, bb, cache_dir, release): k for k, bb in todo}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
            except Exception as e:
                print(f"  FAILED parts {futs[f]}: {e}", flush=True)
            if i % 200 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    files = sorted(cache_dir.glob("*.parquet"))
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True) if files else pd.DataFrame(
        columns=["building_id", "height", "num_floors"])


def apply_part_heights(gdf: gpd.GeoDataFrame, parts: pd.DataFrame,
                       floor_height_m: float = DEFAULT_FLOOR_HEIGHT_M,
                       max_h: float = DEFAULT_MAX_HEIGHT_M, margin_m: float = 1.0) -> gpd.GeoDataFrame:
    """Raise ``height_m`` to the top of the tallest building part when that is taller.

    Overture often models a tower as a ``building_part`` above a low base
    footprint; the base's own ``height`` then understates the building.
    Part top = part ``height`` (else ``num_floors`` × 3 m). Requires
    ``assign_heights`` to have run.
    """
    gdf = gdf.copy()
    if parts.empty:
        return gdf
    ph = pd.to_numeric(parts["height"], errors="coerce").fillna(
        pd.to_numeric(parts["num_floors"], errors="coerce") * floor_height_m)
    ph = ph.where(ph.between(DEFAULT_MIN_HEIGHT_M, max_h))
    top = ph.groupby(parts["building_id"]).max()
    part_top = gdf["id"].map(top)
    taller = part_top.notna() & ((part_top > gdf["height_m"] + margin_m) | (gdf["height_source"] == "assumed"))
    gdf.loc[taller, "height_m"] = part_top[taller].round(1)
    gdf.loc[taller, "height_source"] = "parts"
    return gdf


def load_cached(cache_dir: str | Path) -> gpd.GeoDataFrame:
    files = sorted(Path(cache_dir).glob("*.parquet"))
    parts = [gpd.read_parquet(p) for p in files]
    parts = [p for p in parts if len(p)]
    gdf = pd.concat(parts, ignore_index=True).drop_duplicates(subset="id")
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326").reset_index(drop=True)


# --------------------------------------------------------------------------
# Clean (carried over from the modeling repo)
# --------------------------------------------------------------------------

def clean_footprints(gdf: gpd.GeoDataFrame, projected_crs: str = PROJECTED_CRS,
                     min_area_m2: float = DEFAULT_MIN_AREA_M2) -> gpd.GeoDataFrame:
    """Reproject to a metric CRS, repair invalid geometries, drop slivers and non-polygons."""
    gdf = gdf.to_crs(projected_crs)
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    keep = gdf.geometry.area >= min_area_m2
    return gdf.loc[keep].reset_index(drop=True)


def assign_heights(gdf: gpd.GeoDataFrame, floor_height_m: float = DEFAULT_FLOOR_HEIGHT_M,
                   min_h: float = DEFAULT_MIN_HEIGHT_M, max_h: float = DEFAULT_MAX_HEIGHT_M,
                   assumed_h: float = DEFAULT_ASSUMED_HEIGHT_M) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    h = pd.to_numeric(gdf["height"], errors="coerce")
    h = h.where(h.between(min_h, max_h))
    src = pd.Series(np.where(h.notna(), "overture", None), index=gdf.index, dtype="object")

    floors = pd.to_numeric(gdf["num_floors"], errors="coerce") * floor_height_m
    floors = floors.where(floors.between(min_h, max_h))
    use_f = h.isna() & floors.notna()
    h[use_f] = floors[use_f]
    src[use_f] = "floors"

    src[h.isna()] = "assumed"
    h = h.fillna(assumed_h)
    gdf["height_m"] = h.round(1)
    gdf["height_source"] = src
    return gdf
