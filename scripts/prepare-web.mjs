import { createRequire } from 'node:module'
import { mkdirSync, copyFileSync, existsSync, unlinkSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const target = join(root, 'apps/web/public/engine')
mkdirSync(target, { recursive: true })
// Remove obsolete generated C codec assets left by previous builds.
for (const name of ['g7221.mjs', 'g7221.wasm']) {
  const path = join(target, name)
  if (existsSync(path)) unlinkSync(path)
}

for (const [folder, names] of [
  ['yki-core', ['yki-core.wasm']],
  ['3d', ['yki-3d.wasm']],
]) {
  for (const name of names)
    copyFileSync(join(root, 'packages', folder, 'dist', name), join(target, name))
}
const sdkRequire = createRequire(join(root, 'packages/yki-sdk/package.json'))
const core = resolve(dirname(sdkRequire.resolve('@ffmpeg/core')), '../esm')
for (const name of ['ffmpeg-core.js', 'ffmpeg-core.wasm'])
  copyFileSync(join(core, name), join(target, name))
console.log('Prepared browser engines in apps/web/public/engine')
