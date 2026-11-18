import {useDeferredValue, useEffect, useMemo, useState} from 'react';

import {KeplerMap} from './KeplerMap';
import {Sidebar} from './Sidebar';
import {aggregate, defaultFilters, loadBundle, type Bundle, type Filters} from './data';
import './App.css';

export default function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [filters, setFilters] = useState<Filters | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBundle(import.meta.env.BASE_URL)
      .then(b => {
        setBundle(b);
        setFilters(defaultFilters(b));
      })
      .catch(e => setError(String(e)));
  }, []);

  // Map updates lag the controls slightly so rapid clicks stay responsive.
  const deferred = useDeferredValue(filters);
  const agg = useMemo(() => (bundle && deferred ? aggregate(bundle, deferred) : null), [bundle, deferred]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Bird–Window Collisions in the US &amp; Canada</h1>
        <p>Reported bird–building collisions, attributed to the building where each bird was found.</p>
      </header>
      <div className="app-body">
        {error && <div className="error">Could not load data: {error}</div>}
        {!error && (!bundle || !filters || !agg) && <div className="loading">Loading collision data…</div>}
        {bundle && filters && agg && (
          <>
            <Sidebar bundle={bundle} filters={filters} setFilters={setFilters} agg={agg} />
            <main className="app-map">
              <KeplerMap bundle={bundle} agg={agg} />
            </main>
          </>
        )}
      </div>
    </div>
  );
}
