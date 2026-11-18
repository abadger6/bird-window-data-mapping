// Kepler layer + interaction config, written in code (not exported from the
// kepler.gl demo) so dataset ids and field names stay in sync with data.ts.

import type {Bundle, Aggregate} from './data';

export const DS_BUILDINGS = 'buildings';
export const DS_RECORDS = 'records';
export const DS_CONTEXT = 'context';

// Birds-per-building legend bins (upper bounds). Collision counts are very
// skewed — a few Toronto towers have hundreds, most buildings have 1–2 — so
// fixed bins read better than quantiles and stay stable as filters change.
export const BIRD_BINS: [number, string, string][] = [
  [1, '#FFF3B0', '1'],
  [4, '#FDCB6E', '2–4'],
  [9, '#FC9A4E', '5–9'],
  [24, '#F0603A', '10–24'],
  [99, '#C7254E', '25–99'],
  [1e9, '#7A0B5C', '100+'],
];

export const OUTCOME_COLORS: Record<string, string> = {
  Dead: '#E8575A',
  Alive: '#4FB3BF',
  Unknown: '#A8A8B3',
  Mixed: '#E8B04F',
};

type Field = {name: string; type: string; analyzerType: string; format: string};
const f = (name: string, type: string, analyzerType: string): Field => ({name, type, analyzerType, format: ''});

const BUILDING_FIELDS: Field[] = [
  f('_geojson', 'geojson', 'GEOMETRY'),
  f('building', 'string', 'STRING'),
  f('address', 'string', 'STRING'),
  f('birds', 'integer', 'INT'),
  f('dead', 'integer', 'INT'),
  f('alive', 'integer', 'INT'),
  f('unknown_outcome', 'integer', 'INT'),
  f('reports', 'integer', 'INT'),
  f('first_report', 'string', 'STRING'),
  f('last_report', 'string', 'STRING'),
  f('top_species', 'string', 'STRING'),
  f('height_m', 'real', 'FLOAT'),
  f('height_source', 'string', 'STRING'),
  f('building_class', 'string', 'STRING'),
  f('country', 'string', 'STRING'),
  f('bid', 'integer', 'INT'),
];

const RECORD_FIELDS: Field[] = [
  f('lng', 'real', 'FLOAT'),
  f('lat', 'real', 'FLOAT'),
  f('date', 'string', 'STRING'),
  f('species', 'string', 'STRING'),
  f('outcome', 'string', 'STRING'),
  f('birds', 'integer', 'INT'),
  f('group', 'string', 'STRING'),
  f('side_of_building', 'string', 'STRING'),
  f('building', 'string', 'STRING'),
];

const HEIGHT_SOURCE_LABEL = {
  overture: 'Overture height',
  parts: 'Tallest building part (Overture)',
  floors: 'Estimated from floor count',
  assumed: 'Unknown — shown at 6 m',
} as const;

export function buildingRows(b: Bundle, agg: Aggregate) {
  const rows: unknown[][] = [];
  for (const feat of b.buildings.features) {
    const p = feat.properties;
    const a = agg.perBuilding.get(p.bid);
    if (!a) continue;
    rows.push([
      feat, p.label, p.address ?? '', a.birds, a.dead, a.alive, a.unknown, a.records,
      a.first, a.last, a.topSpecies, p.height_m, HEIGHT_SOURCE_LABEL[p.height_source],
      p.building_class ?? '', p.country ?? '', p.bid,
    ]);
  }
  return {fields: BUILDING_FIELDS, rows};
}

export function recordRows(b: Bundle, agg: Aggregate, buildingLabel: Map<number, string>) {
  const {cols, dicts} = b.records;
  const rows: unknown[][] = new Array(agg.recordIdx.length);
  for (let j = 0; j < agg.recordIdx.length; j++) {
    const i = agg.recordIdx[j];
    const d = cols.dead[i], a = cols.alive[i], u = cols.unknown[i];
    const outcome = d && !a && !u ? 'Dead' : a && !d && !u ? 'Alive' : u && !d && !a ? 'Unknown' : 'Mixed';
    const bid = cols.bid[i];
    rows[j] = [
      cols.lon[i], cols.lat[i], cols.date[i], dicts.species[cols.species[i]], outcome,
      agg.recordBirds[j], dicts.group[cols.group[i]], dicts.side[cols.side[i]],
      bid >= 0 ? buildingLabel.get(bid) ?? '' : `No footprint within ${b.meta.snap_max_m} m`,
    ];
  }
  return {fields: RECORD_FIELDS, rows};
}

const hex = (h: string) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

export function buildConfig() {
  const binColors = BIRD_BINS.map(([, c]) => c);
  return {
    version: 'v1',
    config: {
      visState: {
        filters: [],
        layers: [
          {
            id: 'records_pts',
            type: 'point',
            config: {
              dataId: DS_RECORDS,
              label: 'Individual collision reports',
              color: hex(OUTCOME_COLORS.Dead),
              columns: {lat: 'lat', lng: 'lng'},
              isVisible: true,
              visConfig: {
                radius: 1,
                fixedRadius: false,
                opacity: 0.55,
                outline: false,
                filled: true,
                radiusRange: [0, 50],
                colorRange: {
                  name: 'Outcome',
                  type: 'custom',
                  category: 'Custom',
                  colors: [OUTCOME_COLORS.Alive, OUTCOME_COLORS.Dead, OUTCOME_COLORS.Mixed, OUTCOME_COLORS.Unknown],
                },
              },
            },
            visualChannels: {
              colorField: {name: 'outcome', type: 'string'},
              colorScale: 'ordinal',
            },
          },
          {
            id: 'bld_birds',
            type: 'geojson',
            config: {
              dataId: DS_BUILDINGS,
              label: 'Buildings — birds reported (height = building height)',
              color: hex(BIRD_BINS[2][1]),
              columns: {geojson: '_geojson'},
              isVisible: true,
              visConfig: {
                opacity: 0.95,
                strokeOpacity: 0.8,
                thickness: 0.5,
                strokeColor: [40, 40, 50],
                colorRange: {
                  name: 'Birds per building',
                  type: 'custom',
                  category: 'Custom',
                  colors: binColors,
                  colorMap: BIRD_BINS.map(([v, c]) => [v, c]),
                },
                elevationScale: 1,
                heightRange: [0, 500],
                stroked: false,
                filled: true,
                enable3d: true,
                fixedHeight: true,
                wireframe: false,
              },
            },
            visualChannels: {
              colorField: {name: 'birds', type: 'integer'},
              colorScale: 'custom',
              heightField: {name: 'height_m', type: 'real'},
              heightScale: 'linear',
            },
          },
          {
            id: 'ctx_bld',
            type: 'geojson',
            config: {
              dataId: DS_CONTEXT,
              label: 'Nearby buildings (no reports)',
              color: [78, 80, 96],
              columns: {geojson: '_geojson'},
              isVisible: true,
              visConfig: {
                opacity: 0.55,
                stroked: false,
                filled: true,
                enable3d: true,
                fixedHeight: true,
                elevationScale: 1,
                wireframe: false,
              },
            },
            visualChannels: {
              heightField: {name: 'height_m', type: 'real'},
              heightScale: 'linear',
            },
          },
          {
            id: 'records_heat',
            type: 'heatmap',
            config: {
              dataId: DS_RECORDS,
              label: 'Report density (heatmap)',
              columns: {lat: 'lat', lng: 'lng'},
              isVisible: false,
              visConfig: {opacity: 0.8, radius: 20},
            },
            visualChannels: {weightField: {name: 'birds', type: 'integer'}, weightScale: 'linear'},
          },
        ],
        interactionConfig: {
          tooltip: {
            enabled: true,
            compareMode: false,
            fieldsToShow: {
              [DS_BUILDINGS]: [
                'building', 'address', 'birds', 'dead', 'alive', 'reports', 'top_species',
                'first_report', 'last_report', 'height_m', 'height_source',
              ].map(name => ({name, format: null})),
              [DS_RECORDS]: ['date', 'species', 'outcome', 'birds', 'group', 'side_of_building', 'building']
                .map(name => ({name, format: null})),
              [DS_CONTEXT]: [{name: 'height_m', format: null}],
            },
          },
          brush: {enabled: false, size: 0.5},
          geocoder: {enabled: false},
          coordinate: {enabled: false},
        },
        layerBlending: 'normal',
      },
      mapState: {
        latitude: 44.5,
        longitude: -88,
        zoom: 3.6,
        pitch: 35,
        bearing: 0,
        dragRotate: true,
      },
      mapStyle: {styleType: 'carto_dark'},
    },
  };
}
