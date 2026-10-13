/// <reference lib="webworker" />
import { createCore, fromHex, toHex } from '@nakasyou/yki-core'
import type { Config } from '@nakasyou/yki-core'
import { createYkiSDK, filesLoader } from '@nakasyou/yki-sdk'
import type { YkiSDK } from '@nakasyou/yki-sdk'
const assets = new URL(`${import.meta.env.BASE_URL}engine/`, self.location.origin)
const wasm = fetch(new URL('yki-core.wasm', assets)).then(async (response) => {
  if (!response.ok) throw new Error('YKI エンジンを読み込めません。アセットをビルドしてください。')
  return response.arrayBuffer()
})
let base: Uint8Array | null = null
let sdk: YkiSDK | null = null
let files: Record<string, File | Uint8Array> = {}
const core = wasm.then((bytes) =>
  createCore(bytes, {
    host(request) {
      const value = request as { path: string }
      const file = files[value.path]
      if (!(file instanceof Uint8Array)) throw new Error(`File not loaded: ${value.path}`)
      return { hex: toHex(file) }
    },
  }),
)
async function mediaSDK() {
  if (!sdk)
    sdk = await createYkiSDK({
      wasm: await wasm,
      ffmpegLoad: {
        coreURL: new URL('ffmpeg-core.js', assets).href,
        wasmURL: new URL('ffmpeg-core.wasm', assets).href,
      },
      readFile: (path) => filesLoader(files)(path),
    })
  return sdk
}
let queue = Promise.resolve()
async function handle({
  data,
}: MessageEvent<{ id: number; op: string; data: Record<string, unknown> }>) {
  try {
    let result: unknown
    const engine = await core
    if (data.op === 'load') {
      const candidate = new Uint8Array(data.data.bytes as ArrayBuffer)
      result = engine.request({ op: 'describe', hex: toHex(candidate) })
      base = candidate
      files = { 'base.yki': base }
    } else if (data.op === 'schema') result = engine.schema()
    else {
      if (!base) throw new Error('元の YKI を読み込んでください。')
      if (data.op === 'resolve') result = engine.resolve(base, data.data.id as number, false)
      else if (data.op === 'preview') {
        const asset = engine.request({
          op: 'extract',
          hex: toHex(base),
          resource: data.data.resource as number,
        }) as { hex: string }
        result = engine.decode(fromHex(asset.hex))
      } else if (data.op === 'validateConfig')
        result = engine.validateConfig(data.data.config as Config)
      else if (data.op === 'build' || data.op === 'binary') {
        const config = data.data.config as Config
        files = { ...(data.data.files as Record<string, File>), 'base.yki': base }
        const fields = [
          'songSound',
          'summonSound',
          'nameSound',
          'tribeSound',
          'introSound',
          'postSound',
          'callSound',
        ] as const
        const needsMedia = config.overrides.some(
          (edit) =>
            typeof edit.led === 'string' ||
            fields.some((key) => {
              const value = edit[key]
              return (
                typeof value === 'string' || (value && typeof value === 'object' && 'file' in value)
              )
            }),
        )
        if (needsMedia) result = await (await mediaSDK()).build(config)
        else result = engine.build(config)
        if (data.op === 'binary') {
          const built = result as { data: Uint8Array; manifest: unknown }
          result = {
            ...built,
            inspection: engine.request({ op: 'describe', hex: toHex(built.data) }),
          }
        }
      } else throw new Error('Unknown operation')
    }
    if (data.op === 'binary') {
      const built = result as { data: Uint8Array }
      self.postMessage({ id: data.id, result }, [built.data.buffer as ArrayBuffer])
    } else self.postMessage({ id: data.id, result })
  } catch (error) {
    self.postMessage({ id: data.id, error: error instanceof Error ? error.message : String(error) })
  }
}
self.onmessage = (event) => {
  queue = queue.then(() => handle(event))
}
