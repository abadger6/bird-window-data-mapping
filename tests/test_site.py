import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline import geolibre_project, story

META = {
    "date_min": "1996-03-26", "date_max": "2026-11-17", "generated": "2026-11-18",
    "overture_release": "2026-10-21.0", "excluded": {"total_birds": 10},
    "report_eras": [
        {"file": "reports_1996_2013.parquet", "from": 1996, "to": 2013, "reports": 3, "birds": 3},
        {"file": "reports_2021_2026.parquet", "from": 2021, "to": 2026, "reports": 2, "birds": 2},
    ],
}


def _bldgs():
    return gpd.GeoDataFrame({
        "label": ["Tower A", "Toronto Dominion Bank Tower", "US Plaza"],
        "birds": [100, 40, 9], "birds_fall": [70, 30, 6], "birds_spring": [25, 10, 3],
        "birds_recent": [20, 5, 1], "dead": [80, 20, 5], "height_m": [60.0, 223.0, 30.0],
        "country": ["CA", "CA", "US"],
        "geometry": [box(-79.25, 43.77, -79.249, 43.771), box(-79.381, 43.647, -79.380, 43.648),
                     box(-87.63, 41.88, -87.629, 41.881)],
    }, crs="EPSG:4326")


def _reports():
    return pd.DataFrame({"species": ["Ovenbird", "Ovenbird", "Unknown", "Brown Creeper"],
                         "birds": [3, 1, 5, 2]})


def test_chapters_use_computed_numbers():
    ch = story.build_chapters(_bldgs(), _reports(), META)
    titles = [c.title for c in ch]
    assert titles[0] == "Reported bird–window collisions"
    assert "Tower A: 100 birds" in titles
    assert "Fall migration: 71% of birds" in titles  # 106 / 149
    assert "2 species, mostly small songbirds" in titles  # "Unknown" excluded
    assert any(c.layer == "birds_fall" for c in ch)
    assert "10 birds" in ch[-1].description


def test_project_layers_and_story():
    ch = story.build_chapters(_bldgs(), _reports(), META)
    proj = geolibre_project.build("https://example.org/site/data", ch, META)
    layers = proj["layers"]
    names = [l["name"] for l in layers]
    assert len(names) == len(geolibre_project.BUILDING_SLICES) + len(META["report_eras"])
    # every layer is painted by GeoLibre (not the vector control) and in memory
    assert all(l["metadata"]["controlOwnsPaint"] is False for l in layers)
    assert all(l["metadata"]["vectorState"]["renderMode"] == "geojson" for l in layers)
    assert all(l["source"]["url"].startswith("https://example.org/site/data/") for l in layers)
    visible = [l["name"] for l in layers if l["visible"]]
    assert visible == ["Buildings: birds reported, all years", "Reports 2021–2026 (2)"]
    # species filter is a text match (checkbox lists cap at 200 values)
    pts = [l for l in layers if l["name"].startswith("Reports")]
    assert all(next(q for q in l["quickFilters"] if q["field"] == "species")["kind"] == "text" for l in pts)
    assert len(proj["storymap"]["chapters"]) == len(ch)
    # the last chapter tells GeoLibre readers how to leave the story and explore
    assert "Exit" in proj["storymap"]["chapters"][-1]["description"]
    assert "Exit" not in ch[-1].description  # the standalone story page shows a button instead
    assert len(proj["bookmarks"]) == len(geolibre_project.PLACES)
