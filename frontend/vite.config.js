// frontend/vite.config.js
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  base: '/static/frontend/',

  publicDir: 'public',

  build: {
    outDir: '../static/frontend',
    assetsDir: 'assets',
    manifest: true,
    emptyOutDir: true,

    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.ts'),
        store: resolve(__dirname, 'src/store/main.ts'),
        // Remove payments entry since it's built separately
        payments: resolve(__dirname, 'src/js/payments.js'),
        cart: resolve(__dirname, 'src/cart/cart-detail.ts'),
      },
      output: {
        entryFileNames: 'js/[name]-[hash].js',
        chunkFileNames: 'js/[name]-[hash].js',
        assetFileNames: ({ name }) => {
          const ext = name.split('.').pop();
          if (ext === 'css') return 'css/[name]-[hash].[ext]';
          return 'assets/[name]-[hash].[ext]';
        },
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
    },
  },
});