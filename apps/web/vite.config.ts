import { defineConfig } from 'vite-plus'
import { ripple } from '@ripple-ts/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [ripple({ ssr: false }), tailwindcss()],
  fmt: { semi: false, singleQuote: true },
  server: { host: '127.0.0.1', port: 5173 },
  build: { target: 'esnext' },
  worker: { format: 'es' },
  test: { include: ['src/**/*.test.ts'] },
})
