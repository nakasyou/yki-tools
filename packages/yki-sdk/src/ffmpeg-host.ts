import type { FFmpeg } from '@ffmpeg/ffmpeg'
import type { Json } from '@nakasyou/yki-core'
import { fromHex, toHex } from '@nakasyou/yki-core'
import type { AsyncHost } from './async-core.js'

export type FileSource = Uint8Array | ArrayBuffer | Blob
export type FileLoader = (path: string) => FileSource | Promise<FileSource>
export type FFmpegClient = Pick<
  FFmpeg,
  'exec' | 'writeFile' | 'readFile' | 'deleteFile' | 'on' | 'off'
>
export async function fileBytes(source: FileSource): Promise<Uint8Array> {
  if (source instanceof Uint8Array) return source
  if (source instanceof ArrayBuffer) return new Uint8Array(source)
  return new Uint8Array(await source.arrayBuffer())
}
/** FFmpeg instance must be loaded and dedicated to this host while operations run. */
export function createFFmpegHost(options: { ffmpeg: FFmpegClient; readFile: FileLoader }): {
  host: AsyncHost
  close(): Promise<void>
} {
  const { ffmpeg, readFile } = options
  let counter = 0
  let closed = false
  let accepting = true
  let closing: Promise<void> | undefined
  let queue: Promise<unknown> = Promise.resolve()
  async function run(request: Json): Promise<Json> {
    if (closed) throw new Error('FFmpeg host is closed')
    if (!request || typeof request !== 'object' || Array.isArray(request))
      throw new Error('Invalid host request')
    const r = request as { op: string; path?: string; hex?: string; gain?: number }
    if (r.op === 'read') return { hex: toHex(await fileBytes(await readFile(r.path!))) }
    const prefix = `yki-${counter++}`
    const suffix =
      r.op === 'transcode' ? (r.path!.match(/\.[a-zA-Z0-9]{1,8}$/)?.[0] ?? '.media') : '.pcm'
    const input = `${prefix}${suffix}`
    const output = `${prefix}-output.pcm`
    const logs: string[] = []
    const logger = ({ message }: { message: string }) => logs.push(message)
    ffmpeg.on('log', logger)
    try {
      const bytes =
        r.op === 'transcode' ? await fileBytes(await readFile(r.path!)) : fromHex(r.hex!)
      await ffmpeg.writeFile(input, bytes.slice())
      let args: string[]
      const pcm = ['-f', 's16le', '-ar', '16000', '-ac', '1', '-i', input]
      if (r.op === 'transcode')
        args = [
          '-hide_banner',
          '-loglevel',
          'error',
          '-i',
          input,
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
          output,
        ]
      else if (r.op === 'gain') {
        if (!Number.isFinite(r.gain) || r.gain! < 0) throw new Error('Invalid gain')
        args = [
          '-hide_banner',
          '-loglevel',
          'error',
          ...pcm,
          '-af',
          `volume=${r.gain!.toFixed(9)}`,
          '-c:a',
          'pcm_s16le',
          '-f',
          's16le',
          output,
        ]
      } else if (r.op === 'measure')
        args = [
          '-hide_banner',
          '-loglevel',
          'info',
          '-nostats',
          ...pcm,
          '-af',
          'loudnorm=print_format=json',
          '-f',
          'null',
          '-',
        ]
      else throw new Error(`Unknown host operation: ${r.op}`)
      const status = await ffmpeg.exec(args)
      if (status !== 0)
        throw new Error(`ffmpeg-wasm exited ${status}: ${logs.join('\n').slice(-2000)}`)
      if (r.op !== 'measure') {
        const data = await ffmpeg.readFile(output)
        if (!(data instanceof Uint8Array)) throw new Error('FFmpeg returned text for binary PCM')
        return { hex: toHex(data) }
      }
      const log = logs.join('\n')
      const result = JSON.parse(
        log.slice(log.lastIndexOf('{'), log.lastIndexOf('}') + 1),
      ) as Record<string, string>
      const finite = (value: string | undefined) =>
        value !== undefined && Number.isFinite(Number(value)) ? Number(value) : null
      return {
        lufs: finite(result.input_i),
        true_peak_dbtp: finite(result.input_tp),
        lra: finite(result.input_lra),
      }
    } finally {
      ffmpeg.off('log', logger)
      for (const path of [input, output]) {
        try {
          await ffmpeg.deleteFile(path)
        } catch {
          /* may not exist after failure or measurement */
        }
      }
    }
  }
  const host: AsyncHost = (request) => {
    if (!accepting) return Promise.reject(new Error('FFmpeg host is closed'))
    const result = queue.then(() => run(request))
    queue = result.catch(() => undefined)
    return result
  }
  return {
    host,
    close() {
      accepting = false
      closing ??= queue.then(() => {
        closed = true
      })
      return closing
    },
  }
}
