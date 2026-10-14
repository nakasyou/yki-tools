import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite-plus'
export default defineConfig({
  fmt: { semi: false, singleQuote: true },
  pack: {
    entry: ['src/index.ts', 'src/async-core.ts', 'src/ffmpeg-host.ts'],
    dts: true,
    format: ['esm'],
    sourcemap: true,
    alias: {
      '@nakasyou/yki-3d': fileURLToPath(new URL('../3d/src/index.ts', import.meta.url)),
      '@nakasyou/yki-core': fileURLToPath(new URL('../yki-core/src/index.ts', import.meta.url)),
    },
    deps: { alwaysBundle: ['@nakasyou/yki-core', '@nakasyou/yki-3d'] },
    onSuccess:
      'node ../yki-core/scripts/build.mjs && node ../3d/scripts/build.mjs && node scripts/prepare-browser.mjs',
  },
})
