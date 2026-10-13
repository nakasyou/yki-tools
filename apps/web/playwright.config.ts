import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1440, height: 1000 },
    launchOptions: {
      executablePath: process.env.BROWSER_PATH ?? '/etc/profiles/per-user/nakasyou/bin/brave',
      args: ['--no-sandbox'],
    },
  },
  webServer: {
    command: 'pnpm --dir apps/web run preview',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    cwd: '../..',
  },
})
