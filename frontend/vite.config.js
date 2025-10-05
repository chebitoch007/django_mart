import { defineConfig } from 'vite'
import { resolve } from 'path'

// ✅ Main Vite configuration for Django + Vanilla JS
export default defineConfig({
  root: '.', // base directory
  base: '/static/frontend/', // Django will serve built files here
  build: {
    manifest: true, // generate manifest.json for Django template integration
    outDir: '../static/frontend', // relative to Django static directory
    emptyOutDir: true, // clean before rebuild
    rollupOptions: {
      input: resolve(__dirname, 'src/main.js'), // entry point
    },
  },
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173', // for Django CORS clarity
    watch: {
      usePolling: true, // useful for Ubuntu/WSL/VM setups
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'), // allows you to import like "@/js/payments.js"
    },
  },
})
