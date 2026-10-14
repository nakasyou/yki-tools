import { spawnSync } from 'node:child_process'
import { mkdirSync, copyFileSync } from 'node:fs'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import './medal-template.mjs'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const result = spawnSync('moon', ['build', '--target', 'wasm', '--release'], {
  cwd: root,
  stdio: 'inherit',
})
if (result.status !== 0) process.exit(result.status ?? 1)
mkdirSync(join(root, 'dist'), { recursive: true })
copyFileSync(join(root, '_build/wasm/release/build/wasm/wasm.wasm'), join(root, 'dist/yki-3d.wasm'))
console.log('Built dist/yki-3d.wasm')
