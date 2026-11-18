"""Step 4 — export the published (privacy-filtered) bundle as GeoParquet.

    uv run python scripts/04_export_geoparquet.py

Reads  web/public/data/{buildings.geojson,records.json}
Writes site/data/buildings.parquet  one row per building: totals + ready-made slices
       site/data/buildings.geojson  same buildings, lighter, for the story page
       site/data/sites.geojson      building centre points, for the story page at low zoom
       site/data/reports_<era>.parquet  reports split by era (each < 50k, see REPORT_ERAS)
       site/data/reports.parquet    one row per published report
       site/data/meta.json          provenance + summary numbers

These are for GIS tools (GeoLibre, QGIS, DuckDB). They contain exactly what
the web app publishes, so the private-home exclusion carries over.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web/public/data"
SITE_DATA = ROOT / "site/data"
RECENT_YEARS = 5
REPORT_ERAS = [(1996, 2013), (2014, 2020), (2021, 2026)]  # inclusive years
GEOLIBRE_TILE_THRESHOLD = 50_000  # maplibre-gl-vector DEFAULT_AUTO_THRESHOLD.featureCount
SLICE_COLUMNS = ["birds", "birds_spring", "birds_fall", "birds_recent"]
HEIGHT_SOURCE_LABEL = {
    "overture": "Overture height",
    "parts": "Tallest building part (Overture)",
    "floors": "Estimated from floor count",
    "assumed": "Unknown (drawn at 6 m)",
}


def main() -> int:
    b = gpd.read_file(DATA / "buildings.geojson")
    r = json.loads((DATA / "records.json").read_text())
    c, d = r["cols"], r["dicts"]
    rep = pd.DataFrame({
        "date": pd.to_datetime(c["date"]),
        "species": np.array(d["species"])[c["species"]],
        "dead": c["dead"], "alive": c["alive"], "unknown": c["unknown"],
        "group": np.array(d["group"])[c["group"]],
        "side_of_building": np.array(d["side"])[c["side"]],
        "bid": c["bid"],
        "lon": c["lon"], "lat": c["lat"],
    })
    rep["birds"] = rep[["dead", "alive", "unknown"]].sum(axis=1)
    rep["year"] = rep["date"].dt.year
    m = rep["date"].dt.month
    rep["season"] = np.select([m.between(3, 5), m.isin([6, 7]), m.between(8, 11)],
                              ["Spring", "Summer", "Fall"], "Winter")
    rep["outcome"] = np.select(
        [(rep.dead > 0) & (rep.alive == 0) & (rep.unknown == 0),
         (rep.alive > 0) & (rep.dead == 0) & (rep.unknown == 0),
         (rep.unknown > 0) & (rep.dead == 0) & (rep.alive == 0)],
        ["Dead", "Alive", "Unknown"], "Mixed")
    rep["building"] = rep["bid"].map(b.set_index("bid")["label"])

    known = rep[rep.species != "Unknown"]
    top = (known.groupby(["bid", "species"]).birds.sum().reset_index()
           .sort_values("birds", ascending=False).drop_duplicates("bid").set_index("bid"))
    agg = rep.groupby("bid").agg(birds=("birds", "sum"), dead=("dead", "sum"), alive=("alive", "sum"),
                                 reports=("birds", "size"), first_year=("year", "min"), last_year=("year", "max"))
    # Ready-made slices: GeoLibre filters can't re-total buildings, so each
    # slice the explorer offers is a precomputed column.
    recent_from = int(rep["year"].max()) - (RECENT_YEARS - 1)
    for col, mask in {
        "birds_spring": rep.season.eq("Spring"),
        "birds_fall": rep.season.eq("Fall"),
        "birds_recent": rep.year.ge(recent_from),
    }.items():
        agg[col] = rep[mask].groupby("bid").birds.sum().reindex(agg.index, fill_value=0).astype(int)
    out = b.merge(agg, left_on="bid", right_index=True)
    out["top_species"] = out["bid"].map(top["species"]).fillna("Unknown")
    out["height_source"] = out["height_source"].map(HEIGHT_SOURCE_LABEL)
    out["address"] = out["address"].fillna("")
    out = out[["label", "address", *SLICE_COLUMNS, "dead", "alive", "reports", "first_year", "last_year",
               "top_species", "height_m", "height_source", "country", "geometry"]]

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    out.to_parquet(SITE_DATA / "buildings.parquet")
    # The scroll-driven story page uses plain MapLibre, which reads GeoJSON.
    out[["label", *SLICE_COLUMNS, "height_m", "geometry"]].to_file(
        SITE_DATA / "buildings.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    # Building centre points, so the story page has something to show at
    # continental zoom where 3D footprints are too small to see.
    sites = out[["label", *SLICE_COLUMNS]].copy()
    sites = gpd.GeoDataFrame(sites, geometry=out.geometry.to_crs("ESRI:102008").centroid.to_crs(4326),
                             crs="EPSG:4326")
    sites.to_file(SITE_DATA / "sites.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    pts = gpd.GeoDataFrame(
        rep[["date", "year", "season", "species", "outcome", "birds", "group", "building"]].assign(
            date=rep["date"].dt.strftime("%Y-%m-%d")),
        geometry=gpd.points_from_xy(rep.lon, rep.lat), crs="EPSG:4326")
    pts.to_parquet(SITE_DATA / "reports.parquet")  # everything, for download / SQL

    # GeoLibre switches layers over 50k features to vector tiles, and a tiled
    # layer's quick filters only see the viewport. One file per era keeps each
    # layer in memory so its filters list every value.
    eras = []
    for start, end in REPORT_ERAS:
        part = pts[pts["year"].between(start, end)]
        if len(part) >= GEOLIBRE_TILE_THRESHOLD:
            raise SystemExit(f"era {start}–{end} has {len(part):,} reports; split it so each "
                             f"stays under {GEOLIBRE_TILE_THRESHOLD:,}")
        name = f"reports_{start}_{end}.parquet"
        part.to_parquet(SITE_DATA / name)
        eras.append({"file": name, "from": start, "to": end, "reports": len(part),
                     "birds": int(part["birds"].sum())})

    meta = json.loads((DATA / "meta.json").read_text())
    meta["recent_from_year"] = recent_from
    meta["report_eras"] = eras
    (SITE_DATA / "meta.json").write_text(json.dumps(meta, indent=2))

    for e in eras:
        print(f"{e['file']}: {e['reports']:,} reports")
    for f in ["buildings.parquet", "buildings.geojson", "sites.geojson", "reports.parquet"]:
        print(f"{f}: {(SITE_DATA / f).stat().st_size / 1e6:.1f} MB")
    print(len(out), "buildings,", len(pts), "reports,", int(out.birds.sum()), "birds on buildings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
