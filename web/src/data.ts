// Data loading + client-side filtering/aggregation.
//
// Kepler's own filters work per-dataset, so they can't re-total building
// polygons when the user narrows species or dates. Instead we keep the full
// record table in memory, apply the filters here, and push freshly
// aggregated rows to kepler with replaceDataInMap.

export type Records = {
  n: number;
  dicts: {species: string[]; group: string[]; side: string[]};
  cols: {
    id: number[];
    bid: number[];
    lon: number[];
    lat: number[];
    date: string[];
    species: number[];
    group: number[];
    side: number[];
    dead: number[];
    alive: number[];
    unknown: number[];
  };
};

export type Meta = {
  generated: string;
  overture_release: string;
  date_min: string;
  date_max: string;
  snap_max_m: number;
  records: number;
  excluded: {total_birds: number; home_birds: number; unmatched_birds: number};
  buildings_with_records: number;
  [k: string]: unknown;
};

export type BuildingProps = {
  bid: number;
  label: string;
  name: string | null;
  address: string | null;
  height_m: number;
  height_source: 'overture' | 'parts' | 'floors' | 'assumed';
  building_class: string | null;
  country: string | null;
  overture_id: string;
};

export type BuildingCollection = {
  type: 'FeatureCollection';
  features: {type: 'Feature'; geometry: GeoJSON.Geometry; properties: BuildingProps}[];
};

export type Season = 'Spring' | 'Summer' | 'Fall' | 'Winter';
export const SEASONS: Season[] = ['Spring', 'Summer', 'Fall', 'Winter'];
export const SEASON_MONTHS: Record<Season, string> = {
  Spring: 'Mar–May',
  Summer: 'Jun–Jul',
  Fall: 'Aug–Nov',
  Winter: 'Dec–Feb',
};
export type Outcome = 'dead' | 'alive' | 'unknown';
export const OUTCOMES: Outcome[] = ['dead', 'alive', 'unknown'];

export type Filters = {
  yearMin: number;
  yearMax: number;
  seasons: Set<Season>;
  outcomes: Set<Outcome>;
  species: Set<number>; // empty = all
  groups: Set<number>; // empty = all
};

export type Bundle = {
  records: Records;
  buildings: BuildingCollection;
  context: GeoJSON.FeatureCollection;
  meta: Meta;
  // derived, per record
  year: Int16Array;
  season: Uint8Array;
  yearMin: number;
  yearMax: number;
};

function seasonOfMonth(m: number): number {
  if (m >= 3 && m <= 5) return 0;
  if (m === 6 || m === 7) return 1;
  if (m >= 8 && m <= 11) return 2;
  return 3;
}

export async function loadBundle(base: string): Promise<Bundle> {
  const get = async <T,>(p: string): Promise<T> => {
    const r = await fetch(`${base}data/${p}`);
    if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`);
    return r.json() as Promise<T>;
  };
  const [records, buildings, context, meta] = await Promise.all([
    get<Records>('records.json'),
    get<BuildingCollection>('buildings.geojson'),
    get<GeoJSON.FeatureCollection>('context.geojson'),
    get<Meta>('meta.json'),
  ]);
  const year = new Int16Array(records.n);
  const season = new Uint8Array(records.n);
  let yearMin = 9999;
  let yearMax = 0;
  for (let i = 0; i < records.n; i++) {
    const d = records.cols.date[i];
    const y = +d.slice(0, 4);
    year[i] = y;
    season[i] = seasonOfMonth(+d.slice(5, 7));
    if (y < yearMin) yearMin = y;
    if (y > yearMax) yearMax = y;
  }
  return {records, buildings, context, meta, year, season, yearMin, yearMax};
}

export function defaultFilters(b: Bundle): Filters {
  return {
    yearMin: b.yearMin,
    yearMax: b.yearMax,
    seasons: new Set(SEASONS),
    outcomes: new Set(OUTCOMES),
    species: new Set(),
    groups: new Set(),
  };
}

export type BuildingAgg = {
  birds: number;
  dead: number;
  alive: number;
  unknown: number;
  records: number;
  first: string;
  last: string;
  topSpecies: string;
};

export type Aggregate = {
  /** indices of records passing the filters with ≥1 selected-outcome bird */
  recordIdx: Int32Array;
  /** birds counted for each passing record (respecting outcome filter) */
  recordBirds: Int32Array;
  perBuilding: Map<number, BuildingAgg>;
  totals: {birds: number; dead: number; alive: number; unknown: number; records: number; buildings: number; unmatchedBirds: number};
};

export function aggregate(b: Bundle, f: Filters): Aggregate {
  const {cols, dicts, n} = b.records;
  const seasonOk = SEASONS.map(s => f.seasons.has(s));
  const useDead = f.outcomes.has('dead');
  const useAlive = f.outcomes.has('alive');
  const useUnknown = f.outcomes.has('unknown');
  const allSpecies = f.species.size === 0;
  const allGroups = f.groups.size === 0;

  const idx = new Int32Array(n);
  const birdsArr = new Int32Array(n);
  let k = 0;
  const per = new Map<number, BuildingAgg & {sp: Map<number, number>}>();
  const totals = {birds: 0, dead: 0, alive: 0, unknown: 0, records: 0, buildings: 0, unmatchedBirds: 0};

  for (let i = 0; i < n; i++) {
    const y = b.year[i];
    if (y < f.yearMin || y > f.yearMax) continue;
    if (!seasonOk[b.season[i]]) continue;
    if (!allSpecies && !f.species.has(cols.species[i])) continue;
    if (!allGroups && !f.groups.has(cols.group[i])) continue;
    const d = useDead ? cols.dead[i] : 0;
    const a = useAlive ? cols.alive[i] : 0;
    const u = useUnknown ? cols.unknown[i] : 0;
    const birds = d + a + u;
    if (birds === 0) continue;

    idx[k] = i;
    birdsArr[k] = birds;
    k++;
    totals.birds += birds;
    totals.dead += d;
    totals.alive += a;
    totals.unknown += u;
    totals.records++;

    const bid = cols.bid[i];
    if (bid < 0) {
      totals.unmatchedBirds += birds;
      continue;
    }
    let agg = per.get(bid);
    const date = cols.date[i];
    if (!agg) {
      agg = {birds: 0, dead: 0, alive: 0, unknown: 0, records: 0, first: date, last: date, topSpecies: '', sp: new Map()};
      per.set(bid, agg);
    }
    agg.birds += birds;
    agg.dead += d;
    agg.alive += a;
    agg.unknown += u;
    agg.records++;
    if (date < agg.first) agg.first = date;
    if (date > agg.last) agg.last = date;
    const s = cols.species[i];
    agg.sp.set(s, (agg.sp.get(s) ?? 0) + birds);
  }

  const unknownSpecies = dicts.species.indexOf('Unknown');
  const perBuilding = new Map<number, BuildingAgg>();
  for (const [bid, agg] of per) {
    let best = -1;
    let bestN = 0;
    for (const [s, c] of agg.sp) {
      if (s !== unknownSpecies && c > bestN) {
        best = s;
        bestN = c;
      }
    }
    const {sp: _sp, ...rest} = agg;
    perBuilding.set(bid, {...rest, topSpecies: best >= 0 ? `${dicts.species[best]} (${bestN})` : 'Unknown'});
  }
  totals.buildings = perBuilding.size;
  return {recordIdx: idx.slice(0, k), recordBirds: birdsArr.slice(0, k), perBuilding, totals};
}

/** Count records per species / group under the *other* filters (for list badges). */
export function facetCounts(b: Bundle, f: Filters, facet: 'species' | 'group'): Map<number, number> {
  const relaxed: Filters = {...f, [facet]: new Set<number>()};
  const agg = aggregate(b, relaxed);
  const col = b.records.cols[facet];
  const out = new Map<number, number>();
  for (let j = 0; j < agg.recordIdx.length; j++) {
    const v = col[agg.recordIdx[j]];
    out.set(v, (out.get(v) ?? 0) + agg.recordBirds[j]);
  }
  return out;
}

export function centroidOf(geom: GeoJSON.Geometry): [number, number] {
  // Cheap bbox centre — good enough for fly-to.
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const visit = (c: unknown): void => {
    if (typeof (c as number[])[0] === 'number') {
      const [x, y] = c as number[];
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    } else (c as unknown[]).forEach(visit);
  };
  visit((geom as GeoJSON.Polygon | GeoJSON.MultiPolygon).coordinates);
  return [(minX + maxX) / 2, (minY + maxY) / 2];
}
