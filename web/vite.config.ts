import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages serves the site at https://<user>.github.io/<repo>/, so built
// asset URLs need the repo prefix. Override with BASE_PATH if the repo name
// differs. `npm run dev` serves at /.
const REPO_BASE = process.env.BASE_PATH ?? '/bird-window-data-mapping/';

export default defineConfig(({command}) => ({
  base: command === 'build' ? REPO_BASE : '/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    // kepler.gl is one large bundle; there's no reasonable way to split it further.
    chunkSizeWarningLimit: 12500,
  },
  server: {port: 5173},
  // Some kepler.gl dependencies reach for a Node-style `global`.
  define: {global: 'globalThis'},
}));
