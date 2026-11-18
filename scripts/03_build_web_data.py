"""Step 3 — snap records to buildings and export the web data bundle.

    uv run python scripts/03_build_web_data.py

Reads  data/processed/collisions_clean.parquet, data/cache/buildings/*.parquet
Writes web/public/data/buildings.geojson   footprints with ≥1 attributed record
       web/public/data/context.geojson     other footprints within CONTEXT_M of a record
       web/public/data/records.json        compact columnar record table
       web/public/data/meta.json           provenance + summary numbers
       data/processed/attribution_stats.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402

from pipeline import attribution, buildings, privacy  # noqa: E402

OUT = ROOT / "web/public/data"
CONTEXT_M = 40.0  # grey context buildings shipped around each collision site
PRECISION_DEG = 1e-6  # ~0.1 m


def _round_geoms(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, PRECISION_DEG)
    return gdf[~gdf.geometry.is_empty]


def main() -> int:
    pts = gpd.read_parquet(ROOT / "data/processed/collisions_clean.parquet")
    raw = buildings.load_cached(ROOT / "data/cache/buildings")
    print(f"{len(raw):,} raw footprints from cache", flush=True)

    bl = buildings.clean_footprints(raw)  # projected
    bl = buildings.assign_heights(bl)
    print(f"{len(bl):,} footprints after cleaning", flush=True)

    snapped = attribution.snap_to_buildings(pts.to_crs(bl.crs), bl, buildings.PROJECTED_CRS)
    snapped = snapped.to_crs("EPSG:4326")

    # ---- buildings with records ------------------------------------------
    used = sorted(snapped.loc[snapped.bid >= 0, "bid"].unique())
    remap = {old: new for new, old in enumerate(used)}
    snapped["bid"] = snapped["bid"].map(lambda b: remap.get(b, -1))

    hit = bl.iloc[used].reset_index(drop=True).copy()
    hit["bid"] = range(len(hit))
    addr_mode = (snapped[snapped.bid >= 0].dropna(subset=["building_address"])
                 .groupby("bid")["building_address"]
                 .agg(lambda s: Counter(s).most_common(1)[0][0]))
    hit["address"] = hit["bid"].map(addr_mode)
    hit["label"] = hit["name"].fillna(hit["address"]).fillna("Unnamed building")
    country = snapped[snapped.bid >= 0].groupby("bid")["country"].first()
    hit["country"] = hit["bid"].map(country)

    # Towers modelled as building_parts above a low base footprint.
    release = (ROOT / "data/cache/OVERTURE_RELEASE").read_text().strip()
    parts = buildings.fetch_parts(hit.to_crs("EPSG:4326"), ROOT / "data/cache/building_parts", release=release)
    hit = buildings.apply_part_heights(hit, parts)

    # ---- private-home exclusion (pipeline/privacy.py) --------------------
    snapped_all = snapped.copy()
    home_bids = set(hit.loc[privacy.is_private_home(hit), "bid"])
    birds = snapped[["dead", "alive", "unknown"]].sum(axis=1)
    is_home = snapped["bid"].isin(home_bids)
    is_unmatched = snapped["bid"] < 0
    excluded = {
        "home_buildings": len(home_bids),
        "home_records": int(is_home.sum()),
        "home_birds": int(birds[is_home].sum()),
        "unmatched_records": int(is_unmatched.sum()),
        "unmatched_birds": int(birds[is_unmatched].sum()),
    }
    excluded["total_birds"] = excluded["home_birds"] + excluded["unmatched_birds"]
    snapped = snapped[~is_home & ~is_unmatched].copy()
    keep_bids = sorted(set(hit["bid"]) - home_bids)
    remap2 = {old: new for new, old in enumerate(keep_bids)}
    used = [used[b] for b in keep_bids]  # back to row positions in `bl`
    hit = hit[hit["bid"].isin(keep_bids)].copy()
    hit["bid"] = hit["bid"].map(remap2)
    hit = hit.sort_values("bid").reset_index(drop=True)
    snapped["bid"] = snapped["bid"].map(remap2)

    # ---- context buildings (only around published reports) ----------------
    buf = gpd.GeoDataFrame(geometry=snapped.to_crs(bl.crs).geometry.buffer(CONTEXT_M), crs=bl.crs)
    near = gpd.sjoin(bl[["geometry"]], buf, how="inner", predicate="intersects").index.unique()
    ctx = bl.loc[near.difference(pd.Index(used))].copy()

    # ---- write -------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    hit_out = _round_geoms(hit.to_crs("EPSG:4326"))[
        ["bid", "label", "name", "address", "height_m", "height_source", "class", "country", "id", "geometry"]
    ].rename(columns={"id": "overture_id", "class": "building_class"})
    hit_out.to_file(OUT / "buildings.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    ctx_out = _round_geoms(ctx.to_crs("EPSG:4326"))[["height_m", "geometry"]]
    ctx_out.to_file(OUT / "context.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    # Columnar record table with dictionary-encoded strings (≈4x smaller than CSV).
    def dict_encode(s: pd.Series) -> tuple[list[str], list[int]]:
        cats = s.astype("category")
        return list(cats.cat.categories), cats.cat.codes.astype(int).tolist()

    snapped = snapped.sort_values("date").reset_index(drop=True)
    species_d, species_i = dict_encode(snapped["species"])
    group_d, group_i = dict_encode(snapped["group"])
    side_d, side_i = dict_encode(snapped["side"])
    records = {
        "n": len(snapped),
        "dicts": {"species": species_d, "group": group_d, "side": side_d},
        "cols": {
            "id": snapped["record_id"].tolist(),
            "bid": snapped["bid"].tolist(),
            "lon": snapped["lon"].round(6).tolist(),
            "lat": snapped["lat"].round(6).tolist(),
            "date": snapped["date"].tolist(),
            "species": species_i,
            "group": group_i,
            "side": side_i,
            "dead": snapped["dead"].tolist(),
            "alive": snapped["alive"].tolist(),
            "unknown": snapped["unknown"].tolist(),
        },
    }
    (OUT / "records.json").write_text(json.dumps(records, separators=(",", ":")))

    matched_all = snapped_all.bid >= 0
    stats = {
        # before the private-home exclusion
        "records_clean": int(len(snapped_all)),
        "birds_clean": int(snapped_all[["dead", "alive", "unknown"]].sum().sum()),
        "matched_pct_by_country": (snapped_all.groupby("country")["bid"].apply(lambda b: round(100 * (b >= 0).mean(), 1)).to_dict()),
        "snap_m_median": float(snapped_all.loc[matched_all, "snap_m"].median()),
        "excluded": excluded,
        # what is published
        "records": int(len(snapped)),
        "birds": int(snapped[["dead", "alive", "unknown"]].sum().sum()),
        "buildings_with_records": int(len(hit_out)),
        "context_buildings": int(len(ctx_out)),
        "height_source": hit_out["height_source"].value_counts().to_dict(),
    }
    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "overture_release": (ROOT / "data/cache/OVERTURE_RELEASE").read_text().strip(),
        "date_min": snapped["date"].min(),
        "date_max": snapped["date"].max(),
        "snap_max_m": attribution.SNAP_MAX_M,
        **stats,
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    (ROOT / "data/processed/attribution_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(meta, indent=2))
    for f in ["buildings.geojson", "context.geojson", "records.json"]:
        print(f"{f}: {(OUT / f).stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
