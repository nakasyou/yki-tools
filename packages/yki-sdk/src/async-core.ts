import { createCore, fromHex, toHex } from '@nakasyou/yki-core'
import type { Config, Core, Json, Manifest, MedalId } from '@nakasyou/yki-core'

export type AsyncHost = (request: Json) => Promise<Json>
/** Adapts the synchronous core without SharedArrayBuffer or cross-origin isolation.
 * Completed host calls are replayed from a per-operation transcript; media executes once.
 */
export async function createAsyncCore(wasm: BufferSource | WebAssembly.Module, host: AsyncHost) {
  let transcript: { key: string; reply: Json }[] = []
  let cursor = 0
  let pending: { key: string; request: Json } | undefined
  const core: Core = await createCore(wasm, {
    host(request) {
      const key = JSON.stringify(request)
      const cached = transcript[cursor++]
      if (cached) {
        if (cached.key !== key) throw new Error('Non-deterministic WASM host transcript')
        return cached.reply
      }
      pending = { key, request }
      throw new Error('Async host capability pending')
    },
  })
  let queue: Promise<unknown> = Promise.resolve()
  function request(value: Json): Promise<Json> {
    // Capture the configuration now so caller edits cannot change a running replay.
    const snapshot = JSON.parse(JSON.stringify(value)) as Json
    const job = queue.then(async () => {
      transcript = []
      try {
        for (;;) {
          cursor = 0
          pending = undefined
          try {
            return core.request(snapshot)
          } catch (error) {
            if (!pending) throw error
            const call: { key: string; request: Json } = pending
            let reply: Json
            try {
              reply = await host(call.request)
            } catch (cause) {
              reply = { error: cause instanceof Error ? cause.message : String(cause) }
            }
            transcript.push({ key: call.key, reply })
          }
        }
      } finally {
        transcript = []
        pending = undefined
      }
    })
    queue = job.catch(() => undefined)
    return job
  }
  return {
    request,
    async encodeG7221(pcm: Uint8Array) {
      const reply = (await request({ op: 'g7221_encode', hex: toHex(pcm) })) as { hex: string }
      return fromHex(reply.hex)
    },
    async decodeG7221(payload: Uint8Array) {
      const reply = (await request({ op: 'g7221_decode', hex: toHex(payload) })) as { hex: string }
      return fromHex(reply.hex)
    },
    schema: () => request({ op: 'schema' }),
    validateConfig: (config: Config) =>
      request({ op: 'validate_config', config: config as unknown as Json }),
    inspect: (data: Uint8Array) => request({ op: 'inspect', hex: toHex(data) }),
    async roundtrip(data: Uint8Array) {
      const reply = (await request({ op: 'roundtrip', hex: toHex(data) })) as { hex: string }
      return fromHex(reply.hex)
    },
    resolve: (data: Uint8Array, id: MedalId, strict = false) =>
      request({ op: 'resolve', hex: toHex(data), id: id as unknown as Json, strict }),
    validate: (config: Config, strict = false) =>
      request({ op: 'validate', config: config as unknown as Json, strict }),
    async build(config: Config, strict = false): Promise<{ data: Uint8Array; manifest: Manifest }> {
      const reply = (await request({ op: 'build', config: config as unknown as Json, strict })) as {
        hex: string
        manifest: unknown
      }
      return { data: fromHex(reply.hex), manifest: reply.manifest as Manifest }
    },
    async decode(blob: Uint8Array) {
      const reply = (await request({ op: 'decode', hex: toHex(blob) })) as { hex: string }
      return fromHex(reply.hex)
    },
  }
}
export type AsyncCore = Awaited<ReturnType<typeof createAsyncCore>>
