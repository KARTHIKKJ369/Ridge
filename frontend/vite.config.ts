import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ask': 'http://127.0.0.1:8000',
      '/ingest': 'http://127.0.0.1:8000',
      '/upload': 'http://127.0.0.1:8000',
      '/status': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    }
  }
})
