import { defineConfig } from 'vite-plus'
export default defineConfig({
  fmt: {
    semi: false,
    singleQuote: true,
    ignorePatterns: [
      '**/_build/**',
      '**/dist/**',
      '**/node_modules/**',
      'third_party/**',
      'outputs/**',
      'custom-legacy/**',
      '3d/**',
      'research/**',
    ],
  },
  run: { cache: true },
})
