import { mkdirSync, copyFileSync, existsSync, unlinkSync } from 'node:fs'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const target = join(root, 'dist/browser')
mkdirSync(target, { recursive: true })
// Remove obsolete generated C codec assets left by previous builds.
for (const name of ['g7221.mjs', 'g7221.wasm']) {
  const path = join(target, name)
  if (existsSync(path)) unlinkSync(path)
}

copyFileSync(join(root, '../yki-core/dist/yki-core.wasm'), join(target, 'yki-core.wasm'))
copyFileSync(join(root, '../3d/dist/yki-3d.wasm'), join(target, 'yki-3d.wasm'))
const ffmpeg = resolve(dirname(fileURLToPath(import.meta.resolve('@ffmpeg/core'))), '../esm')
for (const name of ['ffmpeg-core.js', 'ffmpeg-core.wasm'])
  copyFileSync(join(ffmpeg, name), join(target, name))
console.log('Browser assets prepared in dist/browser/ (serve as static files)')
