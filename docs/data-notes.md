# Data notes

Every rule that changes what appears on the map is listed here, with
the numbers from the current build. The figures come from Overture
release 2026-10-21.0 and the FLAP export downloaded 2026-11-17.

## Source

The source is the Global Bird Collision Mapper export
(`Bird_Collision_Data_Map_view_…csv`, now at `data/raw/flap_gbcm_export.csv`).
It has 134,685 rows dated 1996-03-26 to 2026-11-17.

## Cleaning (`pipeline/collisions.py`)

| Step | Rows removed | Remaining |
|---|---:|---:|
| Raw export | | 134,685 |
| Bad coordinates (missing, out of range, 0/0, 3,333,333 placeholders) | 31 | 134,654 |
| No birds (`No Birds Found` patrols, or a bird count of 0) | 12,203 | 122,451 |
| Outside the US or Canada (Overture maritime boundaries) | 1,272 | **121,179** |

- **Coordinates.** The export has two coordinate pairs. `lat`/`lng` are empty
  in 65% of rows, while `x2`/`y2` are filled in on every row, so `x2`/`y2`
  are the primary source and `lng`/`lat` are the fallback.
- **Birds per report** = `max(count_, count_dead + count_alive + count_unknown)`.
  When the dead/alive/unknown breakdown is empty, the birds go to the
  bucket the `status` names: Dead, Died or Scavenged → dead; Alive, Escaped,
  Rehab or Sighted → alive; anything else → unknown.
- **Spellings.** Species and group names that differ only by case or
  whitespace are merged onto the most common spelling, which brings
  717 species names down to 508.
- **Seasons** come from the report's UTC date: Spring is Mar–May, Summer
  Jun–Jul, Fall Aug–Nov and Winter Dec–Feb.
- **Fields removed for privacy:** `notes` (some name building staff),
  `username`, `created_user`, `last_edited_user`, `location` (free text),
  `case_number`, `rehab_centre`, `observations` and `third_party*`. The
  published bundle keeps date, species, outcome counts, side of building,
  monitoring group, building address and coordinates.

The cleaned dataset has **121,179 reports and 123,651 birds**: 106,680 reports
in Canada and 14,499 in the US. After the private-home exclusion described
below, the map publishes **114,386 reports and 116,695 birds at 6,892
buildings**.

## Buildings (`pipeline/buildings.py`)

- **Fetching.** Overture `building` footprints are fetched for each
  0.02° (~2 km) grid cell that contains reports, padded 250 m around those
  reports. That gives 2,833 cells and 1,278,623 footprints, of which
  1,252,838 remain after geometry repair and removing footprints under 20 m².
- **Heights**, as used for the 3D extrusion of the 6,892 published buildings,
  in order of preference:

  | Source | Buildings | Share |
  |---|---:|---:|
  | Overture `height` | 3,974 | 58% |
  | Top of the tallest Overture `building_part` | 846 | 12% |
  | `num_floors` × 3 m | 1,121 | 16% |
  | No height data, drawn at 6 m and labelled in the tooltip | 951 | 14% |

  Overture often models a tower as a separate `building_part` sitting on a
  low base footprint. Reports snap to the base, so the base's own height
  understates the building. Where any part is more than 1 m taller than the
  base, or the base has no height, the building takes the top of its
  tallest part. Part tops come from the part's `height`, or else its
  `num_floors` × 3 m. Example: Consilium Place (Toronto, 9,900 birds) goes
  from 22 m to 64 m.

## Attributing reports to buildings (`pipeline/attribution.py`)

- Each report is snapped to the nearest footprint within **25 m**, the same
  cap used in the earlier CBCM validation work. Distances are measured in
  North America Albers (ESRI:102008).
- **Results:**
  - 118,328 reports (97.6%) were matched: 97.9% in Canada and 95.7% in the US.
  - The median snap distance is 0 m, meaning most report points sit inside
    a footprint.
  - 2,851 reports (2,892 birds) had no footprint in range. They are excluded
    (see below).
- When two footprints are equally close, the first match wins. Each report
  counts toward exactly one building.

## Private-home exclusion (`pipeline/privacy.py`)

The product focuses on larger urban buildings. Publishing reports at
single-family homes would also reveal where individual reporters live. After
snapping, so that a report at a house lands on the house rather than on a
neighbour, reports are removed when:

1. **The building is a home.** Either Overture types it as a house
   (`class` house, detached, semidetached_house, terrace, bungalow, cabin,
   static_caravan, garage or farm, or generic `residential` under 400 m²),
   or it has no type and is under 400 m² and 12 m or lower, which in
   practice means houses, garages and sheds. This removes 2,729 buildings,
   3,942 reports and 4,064 birds.
2. **No footprint lies within 25 m**, so only raw coordinates exist. This
   removes 2,851 reports and 2,892 birds.

In total, **6,793 reports and 6,956 birds (5.6%)** are excluded.

- **Kept regardless of size:** apartments, dormitories, offices, campuses,
  civic buildings and every other non-house type.
- **Grey context buildings** are drawn only around published reports, so they
  don't hint at where excluded reports were.
- **The app discloses the excluded total** as a single number with no
  locations.

## Known limitations

- **These are reports, not risk.** The counts mostly reflect where people
  monitored. Toronto, where FLAP Canada has monitored since the 1990s,
  supplies 79% of the reports (Greater Toronto Area bounding box).
- **Source heights can be wrong.** 14% of buildings have no height and are
  drawn at 6 m. Overture heights can also understate buildings whose towers
  aren't modelled as parts.
- **The home rule is a heuristic.** Some small commercial buildings with no
  type will be dropped, and some homes with unusual tags may remain.
- **Footprint coverage.** Overture coverage outside major cities can miss new
  or small buildings. Reports at those sites are excluded along with the
  other unmatched reports.
