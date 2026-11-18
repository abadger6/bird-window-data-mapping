import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from pipeline import attribution, buildings, collisions


def _raw(**over):
    row = dict(objectid=1, status="Dead", count_=1, count_dead=1, count_alive=0, count_unknown=None,
               x2=-79.38, y2=43.65, lng=None, lat=None, dateutc="2021-09-28T11:00:00",
               species="Ovenbird", side="S", groupname="FLAP Canada", building_address="1 King St",
               notes="found by Edwin", username="someone")
    row.update(over)
    return row


def test_clean_drops_no_birds_and_bad_coords():
    raw = pd.DataFrame([
        _raw(objectid=1),
        _raw(objectid=2, status="No Birds Found", count_=0, count_dead=0),
        _raw(objectid=3, count_=0, count_dead=0, status="Dead"),
        _raw(objectid=4, x2=0.0, y2=0.0),
        _raw(objectid=5, x2=3333333.0, y2=3333333.0),
    ])
    out, stats = collisions.clean(raw)
    assert out["record_id"].tolist() == [1]
    assert stats["dropped_no_birds_found"] == 2
    assert stats["dropped_bad_coordinates"] == 2


def test_clean_strips_pii_columns():
    out, _ = collisions.clean(pd.DataFrame([_raw()]))
    assert list(out.columns) == collisions.PUBLIC_COLUMNS
    assert "notes" not in out and "username" not in out


def test_coordinate_fallback_to_lng_lat():
    out, _ = collisions.clean(pd.DataFrame([_raw(x2=None, y2=None, lng=-87.6, lat=41.9)]))
    assert out.loc[0, "lon"] == -87.6 and out.loc[0, "lat"] == 41.9


@pytest.mark.parametrize("status,dead,alive,unknown", [
    ("Dead", 2, 0, 0), ("Alive", 0, 2, 0), ("Multiple", 0, 0, 2),
])
def test_empty_breakdown_uses_status(status, dead, alive, unknown):
    out, _ = collisions.clean(pd.DataFrame([_raw(status=status, count_=2, count_dead=0, count_alive=0)]))
    assert (out.loc[0, "dead"], out.loc[0, "alive"], out.loc[0, "unknown"]) == (dead, alive, unknown)


def test_birds_is_max_of_count_and_breakdown():
    out, _ = collisions.clean(pd.DataFrame([_raw(count_=1, count_dead=2, count_alive=1)]))
    assert out.loc[0, "birds"] == 3


def test_side_and_season_normalisation():
    out, _ = collisions.clean(pd.DataFrame([_raw(side="S"), _raw(objectid=2, side="North/East", dateutc="2020-04-02")]))
    assert out["side"].tolist() == ["South", "Northeast"]
    assert out["season"].tolist() == ["Fall", "Spring"]


def test_heights_fallback_chain():
    g = gpd.GeoDataFrame({
        "height": [30.0, None, None, 9999.0],
        "num_floors": [None, 4, None, None],
        "geometry": [box(0, 0, 10, 10)] * 4,
    }, crs=buildings.PROJECTED_CRS)
    out = buildings.assign_heights(g)
    assert out["height_m"].tolist() == [30.0, 12.0, 6.0, 6.0]
    assert out["height_source"].tolist() == ["overture", "floors", "assumed", "assumed"]


def test_snap_within_cap_only():
    crs = buildings.PROJECTED_CRS
    bl = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10), box(100, 0, 110, 10)], crs=crs)
    pts = gpd.GeoDataFrame(geometry=[Point(5, 5), Point(30, 5), Point(60, 5)], crs=crs)
    out = attribution.snap_to_buildings(pts, bl, crs, max_m=25)
    assert out["bid"].tolist() == [0, 0, -1]
    assert out["snap_m"].tolist()[:2] == [0.0, 20.0]


def test_species_case_variants_merge_to_most_common():
    raw = pd.DataFrame([_raw(objectid=i, species=s) for i, s in
                        enumerate(["Ovenbird", "Ovenbird", "ovenbird", " OVENBIRD "])])
    out, _ = collisions.clean(raw)
    assert set(out["species"]) == {"Ovenbird"}


def test_part_heights_raise_only_when_taller():
    g = gpd.GeoDataFrame({
        "id": ["a", "b", "c", "d"],
        "height_m": [20.0, 50.0, 6.0, 10.0],
        "height_source": ["overture", "overture", "assumed", "overture"],
        "geometry": [box(0, 0, 10, 10)] * 4,
    }, crs=buildings.PROJECTED_CRS)
    parts = pd.DataFrame({
        "building_id": ["a", "a", "b", "c", "d"],
        "height": [None, 180.0, 30.0, None, 9999.0],
        "num_floors": [10, None, None, 2, None],
    })
    out = buildings.apply_part_heights(g, parts)
    assert out["height_m"].tolist() == [180.0, 50.0, 6.0, 10.0]
    assert out["height_source"].tolist() == ["parts", "overture", "parts", "overture"]


def test_private_home_rule():
    from pipeline import privacy
    sq = lambda side: box(0, 0, side, side)  # noqa: E731
    g = gpd.GeoDataFrame({
        "class":    ["house", "apartments", None,  None,  None,  "residential", "residential", "office"],
        "subtype":  ["residential", "residential", None, None, None, "residential", "residential", "commercial"],
        "height_m": [8.0, 9.0, 6.0, 30.0, 6.0, 6.0, 6.0, 5.0],
        "geometry": [sq(30), sq(10), sq(15), sq(15), sq(40), sq(15), sq(30), sq(10)],
    }, crs=buildings.PROJECTED_CRS)
    # house; small apartment kept; small untyped low; small untyped tall kept;
    # large untyped kept; small generic residential; large generic residential kept; small office kept
    assert privacy.is_private_home(g).tolist() == [True, False, True, False, False, True, False, False]


def test_private_home_rule_requires_metric_crs():
    from pipeline import privacy
    g = gpd.GeoDataFrame({"class": [None], "subtype": [None], "height_m": [5.0]},
                         geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    with pytest.raises(ValueError):
        privacy.is_private_home(g)
