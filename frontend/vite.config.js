// frontend/vite.config.js

import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  // ✅ Set root to frontend folder (not src) so output path resolves correctly
  root: '.',

  // ✅ This is the base URL Django will use to serve Vite-built assets
  base: '/static/frontend/',

  // ✅ Public folder outside root (optional)
  publicDir: 'public',

  build: {
    // ✅ Output to django_mart-main/static/frontend
    outDir: '../static/frontend',

    // ✅ Put images/fonts inside assets/
    assetsDir: 'assets',

    // ✅ Make Django find hashed build files
    manifest: true,

    // ✅ Clears old builds before new one
    emptyOutDir: true,

    rollupOptions: {
      // ✅ Multiple entry points for pages (store, payments, optional main)
      input: {
        main: resolve(__dirname, 'src/main.ts'),              // Optional homepage JS
        store: resolve(__dirname, 'src/store/main.ts'),       // Product pages
        payments: resolve(__dirname, 'src/js/payments.js'),   // Payment scripts
      },
      output: {
        // ✅ Nicely organizes JS output
        entryFileNames: 'js/[name]-[hash].js',
        chunkFileNames: 'js/[name]-[hash].js',

        // ✅ CSS and images go into proper folders
        assetFileNames: ({ name }) => {
          const ext = name.split('.').pop();
          if (ext === 'css') return 'css/[name]-[hash].[ext]';
          return 'assets/[name]-[hash].[ext]';
        },
      },
    },
  },

  // ✅ Run Vite dev server with Django backend
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173',

    // ✅ Allow proxy to Django backend except static frontend path
    proxy: {
      '^/(?!static/frontend)': 'http://localhost:8000',
    },

    // ✅ Required for Linux / WSL file watching
    watch: {
      usePolling: true,
    },
  },

  // ✅ Shortcut paths
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@store': resolve(__dirname, 'src/store'),
    },
  },
});
