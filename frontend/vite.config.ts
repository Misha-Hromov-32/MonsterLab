/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: { main: 'index.html', journal: 'src/styles/journal.css' },
      output: {
        assetFileNames: (asset) =>
          asset.names.includes('journal.css') ? 'journal.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/api', '/articles', '/robots.txt', '/sitemap.xml'].map((path) => [
        path,
        { target: process.env.API_URL ?? 'http://localhost:8000', changeOrigin: true },
      ]),
    ),
  },
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.test.ts'],
  },
})
