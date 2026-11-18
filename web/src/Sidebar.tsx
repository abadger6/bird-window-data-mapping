import {useMemo, useState} from 'react';
import {useDispatch} from 'react-redux';
import {updateMap} from '@kepler.gl/actions';

import type {AppDispatch} from './store';
import {
  OUTCOMES, SEASONS, SEASON_MONTHS, centroidOf, defaultFilters, facetCounts,
  type Aggregate, type Bundle, type Filters, type Outcome, type Season,
} from './data';
import {BIRD_BINS, OUTCOME_COLORS} from './keplerConfig';

const fmt = (n: number) => n.toLocaleString('en-US');

const PLACES: [string, number, number, number][] = [
  ['US + Canada', 44.5, -88, 3.6],
  ['Toronto', 43.66, -79.39, 11.5],
  ['Ottawa', 45.42, -75.7, 12],
  ['Calgary', 51.045, -114.06, 12],
  ['Chicago', 41.885, -87.63, 13],
  ['Minneapolis', 44.975, -93.265, 12.5],
  ['Indianapolis', 39.77, -86.16, 13],
  ['St. Louis', 38.63, -90.24, 11.5],
  ['Northern Utah', 41.0, -111.9, 9],
  ['New York', 40.75, -73.98, 12],
];

const OUTCOME_LABEL: Record<Outcome, string> = {dead: 'Dead', alive: 'Alive', unknown: 'Unknown'};

type Props = {
  bundle: Bundle;
  filters: Filters;
  setFilters: (f: Filters) => void;
  agg: Aggregate;
};

function toggle<T>(s: Set<T>, v: T): Set<T> {
  const n = new Set(s);
  if (n.has(v)) n.delete(v);
  else n.add(v);
  return n;
}

export function Sidebar({bundle, filters, setFilters, agg}: Props) {
  const dispatch = useDispatch<AppDispatch>();
  const {dicts} = bundle.records;
  const [speciesQuery, setSpeciesQuery] = useState('');
  const [showAllGroups, setShowAllGroups] = useState(false);
  const t = agg.totals;

  const flyTo = (lat: number, lon: number, zoom: number, pitch = 50) =>
    dispatch(updateMap({latitude: lat, longitude: lon, zoom, pitch, bearing: zoom > 10 ? -20 : 0}));

  const groupCounts = useMemo(() => facetCounts(bundle, filters, 'group'), [bundle, filters]);
  const speciesCounts = useMemo(() => facetCounts(bundle, filters, 'species'), [bundle, filters]);

  const groupsSorted = useMemo(
    () => dicts.group.map((name, i) => ({i, name, n: groupCounts.get(i) ?? 0})).sort((a, b) => b.n - a.n),
    [dicts.group, groupCounts],
  );
  const speciesMatches = useMemo(() => {
    const q = speciesQuery.trim().toLowerCase();
    return dicts.species
      .map((name, i) => ({i, name, n: speciesCounts.get(i) ?? 0}))
      .filter(s => s.n > 0 && !filters.species.has(s.i) && (!q || s.name.toLowerCase().includes(q)))
      .sort((a, b) => b.n - a.n)
      .slice(0, 8);
  }, [dicts.species, speciesCounts, speciesQuery, filters.species]);

  const topBuildings = useMemo(() => {
    const byBid = new Map(bundle.buildings.features.map(f => [f.properties.bid, f]));
    return [...agg.perBuilding.entries()]
      .sort((a, b) => b[1].birds - a[1].birds)
      .slice(0, 10)
      .map(([bid, a]) => ({feat: byBid.get(bid)!, a}));
  }, [agg, bundle]);

  const years: number[] = [];
  for (let y = bundle.yearMin; y <= bundle.yearMax; y++) years.push(y);
  const pctDead = t.birds ? Math.round((100 * t.dead) / t.birds) : 0;

  return (
    <aside className="sidebar">
      <section className="stats">
        <div><b>{fmt(t.birds)}</b><span>birds reported</span></div>
        <div><b>{fmt(t.buildings)}</b><span>buildings</span></div>
        <div><b>{pctDead}%</b><span>found dead</span></div>
      </section>
      <p className="muted small">
        {fmt(t.records)} reports. To protect reporters' privacy, {fmt(bundle.meta.excluded.total_birds)} birds
        reported at private homes or away from any mapped building are not shown.
      </p>

      <section>
        <h3>Jump to</h3>
        <div className="chips">
          {PLACES.map(([name, lat, lon, z]) => (
            <button key={name} className="chip" onClick={() => flyTo(lat, lon, z, z > 8 ? 50 : 35)}>{name}</button>
          ))}
        </div>
      </section>

      <section>
        <div className="row">
          <h3>Filters</h3>
          <button className="link" onClick={() => { setFilters(defaultFilters(bundle)); setSpeciesQuery(''); }}>Reset</button>
        </div>

        <label className="lbl">Years</label>
        <div className="row gap">
          <select value={filters.yearMin} onChange={e => setFilters({...filters, yearMin: +e.target.value, yearMax: Math.max(+e.target.value, filters.yearMax)})}>
            {years.map(y => <option key={y}>{y}</option>)}
          </select>
          <span className="muted">to</span>
          <select value={filters.yearMax} onChange={e => setFilters({...filters, yearMax: +e.target.value, yearMin: Math.min(+e.target.value, filters.yearMin)})}>
            {years.map(y => <option key={y}>{y}</option>)}
          </select>
        </div>

        <label className="lbl">Season</label>
        <div className="chips">
          {SEASONS.map((s: Season) => (
            <button key={s} title={SEASON_MONTHS[s]} className={`chip ${filters.seasons.has(s) ? 'on' : ''}`}
              onClick={() => setFilters({...filters, seasons: toggle(filters.seasons, s)})}>
              {s} <small>{SEASON_MONTHS[s]}</small>
            </button>
          ))}
        </div>

        <label className="lbl">Outcome</label>
        <div className="chips">
          {OUTCOMES.map(o => (
            <button key={o} className={`chip ${filters.outcomes.has(o) ? 'on' : ''}`}
              onClick={() => setFilters({...filters, outcomes: toggle(filters.outcomes, o)})}>
              <i className="dot" style={{background: OUTCOME_COLORS[OUTCOME_LABEL[o]]}} />{OUTCOME_LABEL[o]}
            </button>
          ))}
        </div>

        <label className="lbl">Species</label>
        {filters.species.size > 0 && (
          <div className="chips">
            {[...filters.species].map(i => (
              <button key={i} className="chip on" onClick={() => setFilters({...filters, species: toggle(filters.species, i)})}>
                {dicts.species[i]} ×
              </button>
            ))}
          </div>
        )}
        <input type="search" placeholder={filters.species.size ? 'Add another species…' : 'All species — search to filter…'}
          value={speciesQuery} onChange={e => setSpeciesQuery(e.target.value)} />
        {speciesQuery && (
          <ul className="list">
            {speciesMatches.map(s => (
              <li key={s.i}>
                <button onClick={() => { setFilters({...filters, species: toggle(filters.species, s.i)}); setSpeciesQuery(''); }}>
                  <span>{s.name}</span><span className="muted">{fmt(s.n)}</span>
                </button>
              </li>
            ))}
            {speciesMatches.length === 0 && <li className="muted small">No matches</li>}
          </ul>
        )}

        <label className="lbl">Monitoring group</label>
        <ul className="list checks">
          {(showAllGroups ? groupsSorted : groupsSorted.slice(0, 8)).map(g => (
            <li key={g.i}>
              <label>
                <input type="checkbox" checked={filters.groups.has(g.i)}
                  onChange={() => setFilters({...filters, groups: toggle(filters.groups, g.i)})} />
                <span>{g.name}</span><span className="muted">{fmt(g.n)}</span>
              </label>
            </li>
          ))}
        </ul>
        <button className="link" onClick={() => setShowAllGroups(!showAllGroups)}>
          {showAllGroups ? 'Show fewer' : `Show all ${dicts.group.length} groups`}
        </button>
        <p className="muted small">None checked = all groups.</p>
      </section>

      <section>
        <h3>Most-reported buildings</h3>
        <ol className="top">
          {topBuildings.map(({feat, a}) => {
            const [lon, lat] = centroidOf(feat.geometry);
            return (
              <li key={feat.properties.bid}>
                <button onClick={() => flyTo(lat, lon, 15.8)}>
                  <span className="name">{feat.properties.label}</span>
                  <span className="n">{fmt(a.birds)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <section>
        <h3>Legend</h3>
        <div className="legend">
          <div className="muted small">Building colour = birds reported · height = building height</div>
          <div className="bins">
            {BIRD_BINS.map(([, c, label]) => (
              <span key={label}><i style={{background: c}} />{label}</span>
            ))}
          </div>
          <div className="muted small" style={{marginTop: 8}}>Points = individual reports, by outcome</div>
          <div className="bins">
            {Object.entries(OUTCOME_COLORS).map(([k, c]) => (
              <span key={k}><i className="dot" style={{background: c}} />{k}</span>
            ))}
          </div>
        </div>
      </section>

      <details className="about">
        <summary>About this data &amp; limitations</summary>
        <p>
          <b>Reports, not risk.</b> Counts reflect where volunteers looked as much as where birds died.
          Toronto (FLAP Canada, monitoring since the 1990s) accounts for most records; a building with no
          reports may simply never have been surveyed.
        </p>
        <p>
          <b>Attribution to buildings.</b> Each report is assigned to the nearest building footprint within{' '}
          {bundle.meta.snap_max_m} m.
        </p>
        <p>
          <b>Private homes are excluded.</b> Reports at houses (Overture house-type buildings, or small untyped
          buildings under 400 m² and 12 m or lower) and reports with no building footprint within{' '}
          {bundle.meta.snap_max_m} m are removed before publishing: {fmt(bundle.meta.excluded.home_birds)} and{' '}
          {fmt(bundle.meta.excluded.unmatched_birds)} birds respectively. Apartments, dormitories, offices and
          campuses are kept.
        </p>
        <p>
          <b>Heights.</b> From Overture Maps, raised to the top of the tallest tower section where Overture
          models one separately. Where missing, estimated from floor count (×3 m), otherwise drawn at 6 m and
          labelled “Unknown” in the tooltip. Some heights are wrong in the source data.
        </p>
        <p>
          <b>Counting.</b> Patrols with no birds found are excluded. Seasons: Spring Mar–May, Summer Jun–Jul,
          Fall Aug–Nov, Winter Dec–Feb (by report date).
        </p>
        <p className="small muted">
          Collision data: Global Bird Collision Mapper, FLAP Canada and partner groups ({bundle.meta.date_min} –{' '}
          {bundle.meta.date_max}). Buildings and boundaries: © Overture Maps Foundation (ODbL), release{' '}
          {bundle.meta.overture_release}. Basemap © CARTO, © OpenStreetMap contributors. Built {bundle.meta.generated}.
        </p>
      </details>
    </aside>
  );
}
