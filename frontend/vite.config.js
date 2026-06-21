import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
// In Docker the backend is reachable via the compose service name, not localhost.
// BACKEND_URL is injected by docker-compose (http://backend:8000); locally it
// falls back to localhost so `npm run dev` against a local backend still works.
const backendTarget = process.env.BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
