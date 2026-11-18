// Mounts <KeplerGl>, registers the three datasets once, then swaps in freshly
// aggregated building + record rows whenever the filters change.

import {useEffect, useMemo, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {addDataToMap, replaceDataInMap} from '@kepler.gl/actions';
import {processGeojson} from '@kepler.gl/processors';
import {KeplerGlSchema} from '@kepler.gl/schemas';
import KeplerGl from '@kepler.gl/components';

import type {AppDispatch} from './store';
import type {Aggregate, Bundle} from './data';
import {DS_BUILDINGS, DS_CONTEXT, DS_RECORDS, buildConfig, buildingRows, recordRows} from './keplerConfig';

type Size = {width: number; height: number};

function useSize(ref: React.RefObject<HTMLDivElement | null>): Size {
  const [size, setSize] = useState<Size>({width: 800, height: 600});
  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const update = () => setSize({width: el.clientWidth, height: el.clientHeight});
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

const DATASET_LABELS = {
  [DS_BUILDINGS]: 'Buildings with reported collisions',
  [DS_RECORDS]: 'Collision reports',
  [DS_CONTEXT]: 'Nearby buildings',
};

export function KeplerMap({bundle, agg}: {bundle: Bundle; agg: Aggregate}) {
  const dispatch = useDispatch<AppDispatch>();
  const containerRef = useRef<HTMLDivElement>(null);
  const size = useSize(containerRef);
  const initialised = useRef(false);

  const labels = useMemo(() => {
    const m = new Map<number, string>();
    for (const f of bundle.buildings.features) m.set(f.properties.bid, f.properties.label);
    return m;
  }, [bundle]);

  useEffect(() => {
    const buildings = buildingRows(bundle, agg);
    const records = recordRows(bundle, agg, labels);

    if (!initialised.current) {
      initialised.current = true;
      const context = processGeojson(bundle.context);
      if (!context) throw new Error('processGeojson(context) returned null');
      dispatch(
        addDataToMap({
          datasets: [
            {info: {id: DS_RECORDS, label: DATASET_LABELS[DS_RECORDS]}, data: records},
            {info: {id: DS_BUILDINGS, label: DATASET_LABELS[DS_BUILDINGS]}, data: buildings},
            {info: {id: DS_CONTEXT, label: DATASET_LABELS[DS_CONTEXT]}, data: context},
          ],
          options: {centerMap: false, readOnly: false},
          config: KeplerGlSchema.parseSavedConfig(buildConfig()) ?? undefined,
        }),
      );
      return;
    }
    for (const [id, data] of [[DS_BUILDINGS, buildings], [DS_RECORDS, records]] as const) {
      dispatch(
        replaceDataInMap({
          datasetToReplaceId: id,
          datasetToUse: {info: {id, label: DATASET_LABELS[id]}, data},
          options: {keepExistingConfig: true, centerMap: false, autoCreateLayers: false},
        }),
      );
    }
  }, [agg, bundle, labels, dispatch]);

  return (
    <div ref={containerRef} style={{width: '100%', height: '100%', position: 'relative'}}>
      <KeplerGl id="birdmap" width={size.width} height={size.height} mapboxApiAccessToken="" />
    </div>
  );
}
