import { defineConfig,loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({mode})=>({
  base: loadEnv(mode,process.cwd(),'VITE_').VITE_PDW_BASE_PATH || '/',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
}))
