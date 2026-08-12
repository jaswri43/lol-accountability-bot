import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Mirrors deploy/nginx.conf's production setup: the frontend always
      // calls relative /api/... paths, and this strips the /api prefix
      // before forwarding to the FastAPI backend. Keeping frontend and API
      // same-origin (from the browser's point of view) in both dev and
      // prod is what lets the httpOnly session cookie from
      // api/auth.py's /auth/callback just work without cross-site cookie
      // headaches -- see that file's docstring.
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
