import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { mkdirSync, copyFileSync } from 'node:fs'

const root = new URL('../', import.meta.url)
const target = new URL('yki_sdk/wasm/', root)
mkdirSync(target, { recursive: true })
for (const [folder, name] of [['yki-core', 'yki-core.wasm'], ['3d', 'yki-3d.wasm']]) {
  const script = new URL(`../${folder}/scripts/build.mjs`, root)
  const result = spawnSync(process.execPath, [fileURLToPath(script)], { stdio: 'inherit' })
  if (result.status !== 0) process.exit(result.status ?? 1)
  copyFileSync(new URL(`../${folder}/dist/${name}`, root), new URL(name, target))
}
console.log('Python SDK WASM assets prepared')
