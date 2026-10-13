import { FFmpeg } from '@ffmpeg/ffmpeg'
import type { FFMessageLoadConfig } from '@ffmpeg/ffmpeg'
import { createAsyncCore } from './async-core.js'
import { createFFmpegHost } from './ffmpeg-host.js'
import type { FileLoader, FileSource } from './ffmpeg-host.js'
export { createAsyncCore } from './async-core.js'
export { createFFmpegHost, fileBytes } from './ffmpeg-host.js'
export { createG7221, createG7221 as loadG7221 } from '@nakasyou/yki-core'
export type { AsyncCore, AsyncHost } from './async-core.js'
export type { FileLoader, FileSource, FFmpegClient } from './ffmpeg-host.js'
export type { G7221Codec } from '@nakasyou/yki-core'
export type {
  Config,
  Manifest,
  MedalId,
  Override,
  AudioOptions,
  Sound,
  Led,
} from '@nakasyou/yki-core'

export interface SDKOptions {
  wasm: BufferSource | WebAssembly.Module
  readFile: FileLoader
  /** Supply a loaded FFmpeg, or specify URLs to load an SDK-owned instance. */
  ffmpeg?: FFmpeg
  ffmpegLoad?: FFMessageLoadConfig
}
/** All public methods return promises; no native ffmpeg or C executable is needed. */
export async function createYkiSDK(options: SDKOptions) {
  const ffmpeg = options.ffmpeg ?? new FFmpeg()
  const owned = options.ffmpeg === undefined
  let adapter: ReturnType<typeof createFFmpegHost> | undefined
  try {
    if (!ffmpeg.loaded) await ffmpeg.load(options.ffmpegLoad)
    adapter = createFFmpegHost({ ffmpeg, readFile: options.readFile })
    const core = await createAsyncCore(options.wasm, adapter.host)
    let closed = false
    let closing: Promise<void> | undefined
    const guard =
      <A extends unknown[], R>(method: (...args: A) => Promise<R>) =>
      (...args: A): Promise<R> => {
        if (closed) return Promise.reject(new Error('YKI SDK is closed'))
        return method(...args)
      }
    return {
      request: guard(core.request),
      encodeG7221: guard(core.encodeG7221),
      decodeG7221: guard(core.decodeG7221),
      schema: guard(core.schema),
      validateConfig: guard(core.validateConfig),
      inspect: guard(core.inspect),
      roundtrip: guard(core.roundtrip),
      resolve: guard(core.resolve),
      validate: guard(core.validate),
      build: guard(core.build),
      decode: guard(core.decode),
      close(): Promise<void> {
        if (closing) return closing
        closed = true
        closing = core
          .schema()
          .then(() => adapter!.close())
          .finally(() => {
            if (owned) ffmpeg.terminate()
          })
        return closing
      },
    }
  } catch (error) {
    if (adapter) await adapter.close()
    if (owned) ffmpeg.terminate()
    throw error
  }
}
export type YkiSDK = Awaited<ReturnType<typeof createYkiSDK>>
/** Logical paths are exact map keys, including @stock/VerN_U.yki for numeric extends. */
export function filesLoader(
  files: ReadonlyMap<string, FileSource> | Readonly<Record<string, FileSource>>,
): FileLoader {
  return (path) => {
    const value =
      files instanceof Map
        ? files.get(path)
        : Object.hasOwn(files, path)
          ? (files as Readonly<Record<string, FileSource>>)[path]
          : undefined
    if (!value) throw new Error(`File not found: ${path}`)
    return value
  }
}
