import { defineConfig } from 'vite-plus'
export default defineConfig({
  fmt: { semi: false, singleQuote: true },
  pack: { entry: ['src/index.ts'], dts: true, format: ['esm'], sourcemap: true, clean: false },
})
