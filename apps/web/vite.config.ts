import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Force re-optimization to prevent stale cache issues
    force: process.env.VITE_DOCKER ? true : false,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8080,
    strictPort: true,
    // For local dev, disable Docker-specific settings
    // Set VITE_DOCKER=true when running in Docker
    host: process.env.VITE_DOCKER ? true : 'localhost',
    // HMR can be flaky in Docker - disable if having issues
    // Set VITE_DISABLE_HMR=true to disable
    hmr: process.env.VITE_DISABLE_HMR
      ? false
      : process.env.VITE_DOCKER
        ? { protocol: 'ws', host: 'localhost', port: 8080 }
        : true,
    watch: process.env.VITE_DOCKER
      ? { usePolling: true, interval: 2000, binaryInterval: 3000 }
      : {},
    proxy: {
      // Proxy target:
      // - Local dev: http://localhost:8000 (default)
      // - Docker: http://backend:8000 (set via VITE_PROXY_TARGET env var)
      // - Production: nginx handles proxying (this config not used)
      // WebSocket endpoint - must be before /api to match first
      '/api/v1/ws': {
        target: proxyTarget,
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
        timeout: 30000, // 30s socket timeout
        proxyTimeout: 30000, // 30s proxy timeout
        configure: (proxy) => {
          // Handle proxy errors to prevent dev server from hanging
          proxy.on('error', (err, req, res) => {
            console.error('Proxy error:', err.message)
            if (res && 'writeHead' in res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({ error: 'Proxy error', message: err.message }))
            }
          })
        },
      },
    },
  },
})
