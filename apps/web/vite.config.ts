import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api/council': {
        target: 'http://127.0.0.1:8765',
        configure(proxy) {
          proxy.on('error', (_error, _request, response) => {
            if (!('writeHead' in response) || response.headersSent) return;
            response.writeHead(503, { 'Content-Type': 'application/json' });
            response.end(JSON.stringify({ error: {
              code: 'service_unavailable',
              message: 'The local Council service is unavailable at 127.0.0.1:8765.',
            } }));
          });
        },
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: { three: ['three'] },
      },
    },
  },
});
