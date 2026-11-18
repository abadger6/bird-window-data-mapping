"""Clean the FLAP Global Bird Collision Mapper export.

Rules (each one is a decision recorded in docs/data-notes.md):

* Coordinates come from ``x2``/``y2`` (populated on every row); the
  ``lng``/``lat`` columns are ~65% empty and are only a fallback.
* Rows with no birds (``status == "No Birds Found"`` or a zero bird count)
  are patrol-effort records, not collisions, and are dropped.
* A record's bird total is ``max(count_, dead + alive + unknown)``. When the
  per-status breakdown is empty, the birds go to the bucket named by
  ``status`` (Dead / Alive), otherwise to "unknown".
* Free-text and identifying fields (notes, usernames, editor accounts,
  location text, case numbers) are not carried forward.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

# Columns that survive into the published product. Everything else in the
# export is either identifying (notes, usernames, editor accounts), internal
# bookkeeping, or near-empty.
PUBLIC_COLUMNS = [
    "record_id",
    "date",
    "year",
    "month",
    "season",
    "species",
    "birds",
    "dead",
    "alive",
    "unknown",
    "side",
    "group",
    "building_address",
    "lon",
    "lat",
]

DEAD_STATUSES = {"dead", "died", "scavenged"}
ALIVE_STATUSES = {"alive", "escaped", "rehab", "sighted"}

SIDE_MAP = {
    "n": "North", "s": "South", "e": "East", "w": "West",
    "ne": "Northeast", "nw": "Northwest", "se": "Southeast", "sw": "Southwest",
    "north/east": "Northeast", "north/west": "Northwest",
    "south/east": "Southeast", "south/west": "Southwest",
}

NO_GROUP = "No group (independent reporter)"


def season_for_month(month: int) -> str:
    """Migration-oriented season. Spring Mar–May, Summer Jun–Jul,
    Fall Aug–Nov, Winter Dec–Feb."""
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7):
        return "Summer"
    if month in (8, 9, 10, 11):
        return "Fall"
    return "Winter"


def load_raw(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")


def _coords(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    lon = pd.to_numeric(df["x2"], errors="coerce").fillna(pd.to_numeric(df.get("lng"), errors="coerce"))
    lat = pd.to_numeric(df["y2"], errors="coerce").fillna(pd.to_numeric(df.get("lat"), errors="coerce"))
    return lon, lat


def _normalize_side(s: pd.Series) -> pd.Series:
    t = s.fillna("Unknown").astype(str).str.strip()
    key = t.str.lower()
    out = key.map(SIDE_MAP).fillna(t.str.title())
    return out.replace({"": "Unknown"})


def canonicalize(s: pd.Series) -> pd.Series:
    """Merge spellings that differ only by case/whitespace ("ovenbird",
    "Ovenbird ") onto the most common spelling."""
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    key = s.str.lower()
    best = (pd.DataFrame({"k": key, "s": s}).value_counts()
            .reset_index().drop_duplicates("k").set_index("k")["s"])
    return key.map(best)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return (clean frame with PUBLIC_COLUMNS, drop-reason counts)."""
    stats: dict[str, int] = {"raw_rows": len(raw)}
    df = raw.copy()

    lon, lat = _coords(df)
    df["lon"], df["lat"] = lon, lat
    bad = (
        lon.isna() | lat.isna()
        | ~lon.between(-180, 180) | ~lat.between(-90, 90)
        | ((lon.abs() < 1) & (lat.abs() < 1))  # "null island" placeholders
    )
    stats["dropped_bad_coordinates"] = int(bad.sum())
    df = df.loc[~bad]

    status = df["status"].fillna("").astype(str).str.strip().str.lower()
    counts = df[["count_", "count_dead", "count_alive", "count_unknown"]].apply(
        pd.to_numeric, errors="coerce").fillna(0).clip(lower=0)
    breakdown = counts.count_dead + counts.count_alive + counts.count_unknown
    birds = np.maximum(counts.count_, breakdown)

    no_birds = status.eq("no birds found") | (birds <= 0)
    stats["dropped_no_birds_found"] = int(no_birds.sum())
    keep = ~no_birds
    df, status, counts, breakdown, birds = (
        df.loc[keep], status[keep], counts[keep], breakdown[keep], birds[keep])

    dead = counts.count_dead.copy()
    alive = counts.count_alive.copy()
    empty = breakdown == 0
    dead[empty & status.isin(DEAD_STATUSES)] = birds[empty & status.isin(DEAD_STATUSES)]
    alive[empty & status.isin(ALIVE_STATUSES)] = birds[empty & status.isin(ALIVE_STATUSES)]
    unknown = (birds - dead - alive).clip(lower=0)

    when = pd.to_datetime(df["dateutc"], errors="coerce", utc=True, format="ISO8601")
    stats["dropped_bad_date"] = int(when.isna().sum())

    out = pd.DataFrame({
        "record_id": df["objectid"].astype("int64"),
        "date": when.dt.strftime("%Y-%m-%d"),
        "year": when.dt.year,
        "month": when.dt.month,
        "species": df["species"].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown"}),
        "birds": birds.astype(int),
        "dead": dead.astype(int),
        "alive": alive.astype(int),
        "unknown": unknown.astype(int),
        "side": _normalize_side(df["side"]),
        "group": df["groupname"].fillna(NO_GROUP).astype(str).str.strip().replace({"": NO_GROUP}),
        "building_address": df["building_address"].astype("string").str.strip(),
        "lon": df["lon"].astype(float),
        "lat": df["lat"].astype(float),
    })
    out["species"] = canonicalize(out["species"])
    out["group"] = canonicalize(out["group"])
    out = out.loc[when.notna().values].copy()
    out["year"] = out["year"].astype(int)
    out["month"] = out["month"].astype(int)
    out["season"] = out["month"].map(season_for_month)
    stats["clean_rows"] = len(out)
    return out[PUBLIC_COLUMNS].reset_index(drop=True), stats


def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")


def clip_to_boundary(points: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep points inside the boundary polygons; adds a ``country`` column."""
    joined = gpd.sjoin(points, boundary[["country", "geometry"]], how="inner", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined.drop(columns="index_right")
