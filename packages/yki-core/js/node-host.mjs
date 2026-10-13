import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { fromHex, toHex } from './index.mjs'
const here = dirname(fileURLToPath(import.meta.url))
const project = resolve(here, '..')
const repository = resolve(project, '../..')
function command(executable, args) {
  const result = spawnSync(executable, args, { maxBuffer: 128_000_000 })
  if (result.error)
    throw new Error(`Required executable failed: ${executable}: ${result.error.message}`)
  if (result.status !== 0)
    throw new Error(`${executable} failed: ${result.stderr.toString().slice(-2000)}`)
  return result
}
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex')
/** File I/O, transcoding and loudness measurement; codecs run inside MoonBit. */
export function createNodeHost({
  baseDir = process.cwd(),
  stockDir = resolve(repository, 'yki'),
  ffmpeg = 'ffmpeg',
} = {}) {
  const temporary = mkdtempSync(join(tmpdir(), 'yki-core-'))
  let closed = false
  const pathFor = (path) =>
    path.startsWith('@stock/') ? resolve(stockDir, path.slice(7)) : resolve(baseDir, path)
  function pcmCommand(raw, args) {
    const input = join(temporary, 'input.pcm')
    writeFileSync(input, raw)
    return command(ffmpeg, [
      '-hide_banner',
      '-nostats',
      '-f',
      's16le',
      '-ar',
      '16000',
      '-ac',
      '1',
      '-i',
      input,
      ...args,
    ])
  }
  function host(request) {
    if (closed) throw new Error('Node host is closed')
    switch (request.op) {
      case 'read':
        return { hex: toHex(readFileSync(pathFor(request.path))) }
      case 'transcode': {
        const path = pathFor(request.path)
        const source = readFileSync(path)
        const out = join(temporary, 'transcode.pcm')
        command(ffmpeg, [
          '-hide_banner',
          '-loglevel',
          'error',
          '-y',
          '-i',
          path,
          '-map',
          '0:a:0',
          '-ar',
          '16000',
          '-ac',
          '1',
          '-c:a',
          'pcm_s16le',
          '-f',
          's16le',
          out,
        ])
        return { hex: toHex(readFileSync(out)), sha256: sha(source) }
      }
      case 'gain': {
        const out = join(temporary, 'gain.pcm')
        pcmCommand(fromHex(request.hex), [
          '-loglevel',
          'error',
          '-y',
          '-af',
          `volume=${request.gain.toFixed(9)}`,
          '-c:a',
          'pcm_s16le',
          '-f',
          's16le',
          out,
        ])
        return { hex: toHex(readFileSync(out)) }
      }
      case 'measure': {
        const stderr = pcmCommand(fromHex(request.hex), [
          '-af',
          'loudnorm=print_format=json',
          '-f',
          'null',
          '-',
        ]).stderr.toString()
        const result = JSON.parse(
          stderr.slice(stderr.lastIndexOf('{'), stderr.lastIndexOf('}') + 1),
        )
        const finite = (value) => (Number.isFinite(Number(value)) ? Number(value) : null)
        return {
          lufs: finite(result.input_i),
          true_peak_dbtp: finite(result.input_tp),
          lra: finite(result.input_lra),
        }
      }
      default:
        throw new Error(`Unknown host operation: ${request.op}`)
    }
  }
  return {
    host,
    resolvePath: pathFor,
    close() {
      if (!closed) rmSync(temporary, { recursive: true, force: true })
      closed = true
    },
  }
}
