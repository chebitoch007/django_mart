// frontend/vite.config.js - FIXED: Remove duplicate main.ts entry
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  base: '/static/frontend/',

  build: {
    outDir: '../static/frontend',
    assetsDir: '',
    manifest: 'manifest.json',
    emptyOutDir: true,

    rollupOptions: {
      input: {
        // ❌ REMOVED: 'src/main': resolve(__dirname, 'src/main.ts'),
        // This was causing CartManager to initialize twice!

        // ✅ KEEP THESE:
        'src/store/main': resolve(__dirname, 'src/store/main.ts'),
        'src/payments/payments': resolve(__dirname, 'src/payments/payments.ts'),
        'src/cart/cart-detail': resolve(__dirname, 'src/cart/cart-detail.ts'),
      },
      output: {
        entryFileNames: 'js/[name].[hash].js',
        chunkFileNames: 'js/[name].[hash].js',
        assetFileNames: 'css/[name].[hash].[ext]',
      },
    },
  },

  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173',
    proxy: {
      '^/(?!static/frontend)': 'http://localhost:8000',
    },
    watch: { usePolling: true },
  },

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@store': resolve(__dirname, 'src/store'),
      '@cart': resolve(__dirname, 'src/cart'),
      '@payments': resolve(__dirname, 'src/payments'),
    },
  },
});