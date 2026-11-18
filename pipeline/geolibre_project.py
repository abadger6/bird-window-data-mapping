"""Build the GeoLibre explorer project (`.geolibre`) from the published data.

Uses the official ``geolibre`` Python package so the file matches what the
app writes. Layers read the GeoParquet files by URL; nothing is inlined.

Layers, top to bottom:
    Reports (3 eras)     points coloured by outcome, with quick filters; latest era on
    Buildings (4 views)  3D, height = building height, colour = birds;
                         one layer per ready-made slice, only "All years" on
"""
from __future__ import annotations

from geolibre import authoring, project as gp

from pipeline.story import Chapter

BIRD_STOPS = [  # lower bounds, matching the legend used everywhere else
    (1, "#FFF3B0", "1"), (2, "#FDCB6E", "2–4"), (5, "#FC9A4E", "5–9"),
    (10, "#F0603A", "10–24"), (25, "#C7254E", "25–99"), (100, "#7A0B5C", "100+"),
]
OUTCOME_COLORS = {"Dead": "#E8575A", "Alive": "#4FB3BF", "Unknown": "#A8A8B3", "Mixed": "#E8B04F"}

BUILDING_SLICES = [  # (column, layer name)
    ("birds", "Buildings: birds reported, all years"),
    ("birds_fall", "Buildings: fall migration (Aug–Nov)"),
    ("birds_spring", "Buildings: spring migration (Mar–May)"),
    ("birds_recent", "Buildings: last 5 years"),
]

PLACES = [  # bookmarks: name, lng, lat, zoom, pitch, bearing
    ("US + Canada", -88.0, 44.5, 3.4, 0, 0),
    ("Toronto (downtown)", -79.381, 43.6475, 14.6, 55, -20),
    ("Toronto (North York)", -79.408, 43.745, 14.6, 55, -20),
    ("Ottawa", -75.70, 45.42, 13.5, 50, 0),
    ("Calgary", -114.065, 51.047, 13.5, 50, 0),
    ("Chicago", -87.63, 41.882, 14.2, 55, -20),
    ("Minneapolis", -93.265, 44.975, 13.5, 50, 0),
    ("Indianapolis", -86.165, 39.773, 13.5, 50, 0),
    ("St. Louis", -90.24, 38.63, 12.5, 50, 0),
    ("New York", -73.98, 40.755, 13.5, 50, 0),
]

BASEMAP = "dark"


def _app_painted_layer(name: str, url: str) -> dict:
    """A GeoParquet layer loaded into memory and painted by GeoLibre itself.

    ``gp.vector_layer`` marks layers ``controlOwnsPaint``, which the app means
    for tiled or oversized layers the vector control keeps. Then GeoLibre's
    own symbology (graduated/categorized colour, extrusion) is not applied.
    Every file we publish stays under the 50k-feature tiling threshold (see
    scripts/04_export_geoparquet.py), so the app can paint them.
    """
    layer = gp.vector_layer(name, url, render_mode="geojson")
    layer["metadata"]["controlOwnsPaint"] = False
    return layer


def _building_layer(url: str, column: str, name: str, visible: bool) -> dict:
    layer = _app_painted_layer(name, url)
    layer["visible"] = visible
    layer["filterExpression"] = [">", ["get", column], 0]
    layer["quickFilters"] = [
        {"id": "country", "field": "country", "kind": "categorical", "values": []},
        {"id": "height", "field": "height_m", "kind": "range", "min": None, "max": None},
    ]
    return layer


def _building_style(column: str) -> dict:
    return {
        "vectorStyleMode": "graduated",
        "vectorStyleProperty": column,
        "vectorStyleClassCount": len(BIRD_STOPS),
        "vectorStyleClassificationScheme": "manual",
        "vectorStyleStops": [{"value": v, "color": c, "label": lab} for v, c, lab in BIRD_STOPS],
        "extrusionEnabled": True,
        "extrusionHeightProperty": "height_m",
        "extrusionHeightScale": 1,
        "extrusionBase": 0,
        "extrusionOpacity": 0.9,
    }


def _set_report_popup(proj: dict, layer_id: str) -> None:
    authoring.set_popup(proj, layer_id, [
        gp.popup_field("date", label="Date", hover=True),
        gp.popup_field("species", label="Species", hover=True),
        gp.popup_field("outcome", label="Outcome"),
        gp.popup_field("birds", label="Birds", kind="number"),
        gp.popup_field("group", label="Reported by"),
        gp.popup_field("building", label="Building"),
    ], click=True, hover=True)


def build(data_url: str, chapters: list[Chapter], meta: dict) -> dict:
    """Return the project dict. ``data_url`` is the public base URL of site/data/."""
    data_url = data_url.rstrip("/") + "/"
    proj = gp.build_empty_project("Bird–Window Collisions (US & Canada)", center=[-88.0, 44.5], zoom=3.4)
    authoring.set_basemap(proj, BASEMAP)

    # Buildings first, so the points layer added last draws on top.
    slice_ids: dict[str, str] = {}
    for column, name in BUILDING_SLICES:
        lid = authoring.add_layer(proj, _building_layer(data_url + "buildings.parquet", column, name,
                                                        visible=(column == "birds")))
        authoring.apply_style(proj, lid, _building_style(column))
        authoring.set_popup(proj, lid, [
            gp.popup_field("address", label="Address"),
            gp.popup_field(column, label="Birds reported (this view)", kind="number", thousands=True, hover=True),
            gp.popup_field("birds", label="Birds reported, all years", kind="number", thousands=True),
            gp.popup_field("dead", label="Found dead", kind="number", thousands=True),
            gp.popup_field("alive", label="Found alive", kind="number", thousands=True),
            gp.popup_field("reports", label="Reports", kind="number", thousands=True),
            gp.popup_field("top_species", label="Most-reported species"),
            gp.popup_field("first_year", label="First report"),
            gp.popup_field("last_year", label="Latest report"),
            gp.popup_field("height_m", label="Height", kind="number", decimals=0, suffix=" m"),
            gp.popup_field("height_source", label="Height source"),
        ], click=True, hover=True, title_expression="{label}")
        slice_ids[column] = lid

    # Report points: one layer per era (each under GeoLibre's tiling threshold,
    # so quick filters list every value). Only the latest era starts visible.
    eras = meta["report_eras"]
    pts_ids: list[str] = []
    for i, era in enumerate(eras):
        pts = _app_painted_layer(f"Reports {era['from']}–{era['to']} ({era['reports']:,})",
                                 data_url + era["file"])
        pts["visible"] = i == len(eras) - 1
        pts["quickFilters"] = [
            # Text match, not checkboxes: GeoLibre caps checkbox lists at 200 distinct
            # values and recent eras have 300+ species. "warbler" matches every warbler.
            {"id": "species", "field": "species", "kind": "text", "operator": "contains", "text": ""},
            {"id": "outcome", "field": "outcome", "kind": "categorical", "values": []},
            {"id": "season", "field": "season", "kind": "categorical", "values": []},
            {"id": "year", "field": "year", "kind": "range", "min": None, "max": None},
            {"id": "group", "field": "group", "kind": "categorical", "values": []},
        ]
        pid = authoring.add_layer(proj, pts)
        authoring.apply_style(proj, pid, {
            "vectorStyleMode": "categorized",
            "vectorStyleProperty": "outcome",
            "vectorStyleStops": [{"value": k, "color": c, "label": k} for k, c in OUTCOME_COLORS.items()],
            "circleRadius": 3,
            "strokeWidth": 0,
            "fillOpacity": 0.75,
        })
        _set_report_popup(proj, pid)
        pts_ids.append(pid)

    for name, lng, lat, zoom, pitch, bearing in PLACES:
        authoring.add_bookmark(proj, name, center=[lng, lat], zoom=zoom, pitch=pitch, bearing=bearing)

    # ---- story map --------------------------------------------------------
    authoring.set_story_map(
        proj,
        title="Bird–Window Collisions in the US & Canada",
        subtitle=f"{meta['date_min'][:4]}–{meta['date_max'][:4]} · reports attributed to buildings",
        footer=("Collision reports: <a href=\"https://www.birdmapper.org\">Global Bird Collision Mapper</a> "
                "(FLAP Canada and partners). "
                "Buildings: © Overture Maps Foundation (ODbL)."),
        theme="dark",
        start_slide="global",
    )
    for c in chapters:
        enter = [{"layerId": slice_ids[col], "opacity": 1.0 if col == c.layer else 0.0, "duration": 1200}
                 for col in slice_ids]
        enter += [{"layerId": pid, "opacity": 1.0 if c.show_points else 0.0, "duration": 1200}
                  for pid in pts_ids]
        authoring.add_story_chapter(
            proj, c.title, description=c.geolibre_note + c.description, center=list(c.center), zoom=c.zoom,
            pitch=c.pitch, bearing=c.bearing, alignment=c.alignment, on_enter=enter, chapter_id=c.id,
        )

    authoring.set_view(proj, center=[-88.0, 44.5], zoom=3.4, pitch=0, bearing=0)
    proj.setdefault("metadata", {}).update({
        "source": "bird-window-data-mapping pipeline (scripts/05_build_site.py)",
        "generated": meta["generated"],
        "overture_release": meta["overture_release"],
    })
    return proj
