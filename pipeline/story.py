"""Story map chapters, defined once.

The same chapters are written into the GeoLibre project (presented in-app
from Project → Story map) and into ``site/story/chapters.json`` for the
standalone scroll-driven story page. Numbers are computed from the published
data at build time, never typed in by hand.

Each chapter names the building ``layer`` it shows: one of the slice columns
in ``site/data/buildings.parquet`` (``birds``, ``birds_fall``,
``birds_spring``, ``birds_recent``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import geopandas as gpd
import pandas as pd


@dataclass
class Chapter:
    id: str
    title: str
    description: str  # inline HTML allowed
    center: tuple[float, float]  # lng, lat
    zoom: float
    pitch: float = 0
    bearing: float = 0
    layer: str = "birds"  # building slice column shown in this chapter
    show_points: bool = False
    alignment: str = "left"
    # Extra text shown only in the GeoLibre presentation (e.g. how to leave the
    # story and explore); the standalone story page shows a button instead.
    geolibre_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _centroid(bldgs: gpd.GeoDataFrame, label: str) -> tuple[float, float]:
    row = bldgs[bldgs["label"] == label].sort_values("birds", ascending=False).iloc[0]
    c = gpd.GeoSeries([row.geometry], crs=bldgs.crs).to_crs("ESRI:102008").centroid.to_crs(4326).iloc[0]
    return (round(c.x, 5), round(c.y, 5))


def build_chapters(bldgs: gpd.GeoDataFrame, reports: pd.DataFrame, meta: dict) -> list[Chapter]:
    total = bldgs["birds"].sum()
    fall, spring = bldgs["birds_fall"].sum(), bldgs["birds_spring"].sum()
    dead_share = bldgs["dead"].sum() / total
    top = bldgs.sort_values("birds", ascending=False).iloc[0]
    tdc = bldgs[bldgs["label"] == "Toronto Dominion Bank Tower"]
    species = (reports[reports["species"] != "Unknown"].groupby("species")["birds"].sum()
               .sort_values(ascending=False))
    n_species = reports.loc[reports["species"] != "Unknown", "species"].nunique()
    us = bldgs[bldgs["country"] == "US"].sort_values("birds", ascending=False)
    us_top = us.iloc[0]
    excluded = meta["excluded"]["total_birds"]
    y0, y1 = meta["date_min"][:4], meta["date_max"][:4]

    ch = [
        Chapter(
            "overview", "Reported bird–window collisions",
            f"Volunteers and building staff have reported <b>{_fmt(total)} birds</b> that struck "
            f"<b>{_fmt(len(bldgs))} buildings</b> across the US and Canada between {y0} and {y1}. "
            f"{round(100 * dead_share)}% were found dead.<br><br>"
            "These are <i>reports</i>, not a census: a building with no reports may simply never "
            "have been checked.",
            (-88.0, 44.5), 3.4, 0, 0, show_points=True),
        Chapter(
            "toronto", "Toronto: decades of dawn patrols",
            "Most reports come from Toronto, where FLAP Canada volunteers have walked downtown "
            "and suburban office districts at dawn for decades. Each block is a building drawn "
            "at its real height, coloured by birds reported.",
            (-79.381, 43.6475), 14.6, 55, -20),
        Chapter(
            "top", f"{top['label']}: {_fmt(top['birds'])} birds",
            f"The most-reported site, {top['label']}, is a cluster of mid-rise office towers in "
            f"north-east Toronto. Height isn't the only factor: glass and nearby trees draw "
            f"birds in at eye level.",
            _centroid(bldgs, top["label"]), 16.2, 60, 30),
    ]
    if len(tdc):
        t = tdc.iloc[0]
        ch.append(Chapter(
            "tower", f"Tall and glassy: {_fmt(t['birds'])} birds",
            f"The Toronto Dominion Bank Tower ({round(t['height_m'])} m) is one of the most-reported "
            "skyscrapers. Reflective glass mirrors sky and trees, and lit windows at night pull "
            "migrating birds off course.",
            _centroid(bldgs, "Toronto Dominion Bank Tower"), 16.4, 62, -35))
    ch += [
        Chapter(
            "fall", f"Fall migration: {round(100 * fall / total)}% of birds",
            f"{_fmt(fall)} of the birds were reported from August to November, when young birds "
            f"make their first migration south. Spring (March–May) accounts for "
            f"{round(100 * spring / total)}%. This view shows fall reports only.",
            (-79.39, 43.68), 11.6, 45, -15, layer="birds_fall"),
        Chapter(
            "species", f"{n_species} species, mostly small songbirds",
            "The most-reported species: " + ", ".join(
                f"{s} ({_fmt(n)})" for s, n in species.head(5).items())
            + ". Night-migrating sparrows, kinglets and warblers are especially vulnerable.",
            (-79.39, 43.68), 11.6, 45, -15, show_points=True),
        Chapter(
            "us", f"Beyond Toronto: {_fmt(us['birds'].sum())} birds at US buildings",
            f"Monitoring groups in Chicago, St. Louis, Minneapolis, Indianapolis and elsewhere "
            f"report too. In the US, {us_top['label']} has the most reports ({_fmt(us_top['birds'])}).",
            _centroid(bldgs, us_top["label"]), 15.4, 55, -20),
        Chapter(
            "close", "Your turn: explore the data",
            "Switch between all-years, fall, spring and last-5-years building views; filter "
            "reports by species, season, outcome and monitoring group; and jump between cities "
            "with bookmarks. Click any building or point for details.<br><br>"
            f"<small>To protect reporters' privacy, {_fmt(excluded)} birds reported at private "
            "homes or away from any mapped building are not shown.</small>",
            (-88.0, 44.5), 3.4, 0, 0, show_points=True,
            geolibre_note="<b>Click Exit (top left) or press Esc</b> to close the story. "
                          "The map stays open for you to explore; layers and filters are in "
                          "the Layers panel.<br><br>"),
    ]
    return ch
