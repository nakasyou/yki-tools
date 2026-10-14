// Portable ES module: no Node imports. Media and files are synchronous host RPCs.
const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', { fatal: true })
export function toHex(bytes) {
  const digits = '0123456789abcdef'
  const encoded = new Uint8Array(bytes.length * 2)
  for (let i = 0; i < bytes.length; i++) {
    encoded[2 * i] = digits.charCodeAt(bytes[i] >>> 4)
    encoded[2 * i + 1] = digits.charCodeAt(bytes[i] & 15)
  }
  return decoder.decode(encoded)
}
export function fromHex(text) {
  if (typeof text !== 'string' || text.length % 2 || !/^[0-9a-f]*$/i.test(text))
    throw new Error('Invalid hex')
  const bytes = new Uint8Array(text.length / 2)
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(text.slice(2 * i, 2 * i + 2), 16)
  return bytes
}
function send(exports, bytes, begin, write) {
  if (exports[begin](bytes.length) !== 0) throw new Error('WASM request exceeds 256 MB')
  for (let p = 0; p < bytes.length; p += 4) {
    const word =
      bytes[p] |
      ((bytes[p + 1] ?? 0) << 8) |
      ((bytes[p + 2] ?? 0) << 16) |
      ((bytes[p + 3] ?? 0) << 24)
    exports[write](p, word)
  }
}
function receive(exports, length, read) {
  const bytes = new Uint8Array(exports[length]())
  for (let p = 0; p < bytes.length; p += 4) {
    const word = exports[read](p)
    for (let i = 0; i < 4 && p + i < bytes.length; i++) bytes[p + i] = word >>> (i * 8)
  }
  return bytes
}
/** Create an independent WASM instance. host(request) returns a JSON value synchronously. */
export async function createCore(wasm, { host } = {}) {
  let exports
  let active = false
  const imports = {
    yki_host: {
      rpc() {
        let reply
        try {
          const request = JSON.parse(
            decoder.decode(receive(exports, 'host_request_length', 'host_request_read')),
          )
          if (!host) throw new Error(`Host capability required: ${request.op}`)
          reply = host(request)
          if (reply && typeof reply.then === 'function')
            throw new Error('Host RPC must be synchronous')
        } catch (error) {
          reply = { error: String(error.message ?? error) }
        }
        send(
          exports,
          encoder.encode(JSON.stringify(reply)),
          'host_response_begin',
          'host_response_write',
        )
        return 0
      },
    },
  }
  const result = await WebAssembly.instantiate(wasm, imports)
  exports = (result.instance ?? result).exports
  function request(value) {
    if (active)
      throw new Error(
        'Recursive calls on one core instance are unsupported; create another instance',
      )
    active = true
    try {
      send(exports, encoder.encode(JSON.stringify(value)), 'input_begin', 'input_write')
      exports.invoke()
      const response = JSON.parse(decoder.decode(receive(exports, 'output_length', 'output_read')))
      if (response.error) throw new Error(response.error)
      return response
    } finally {
      active = false
    }
  }
  return {
    request,
    encodeG7221: (pcm) => fromHex(request({ op: 'g7221_encode', hex: toHex(pcm) }).hex),
    decodeG7221: (payload) => fromHex(request({ op: 'g7221_decode', hex: toHex(payload) }).hex),
    schema: () => request({ op: 'schema' }),
    validateConfig: (config) => request({ op: 'validate_config', config }),
    inspect: (data) => request({ op: 'inspect', hex: toHex(data) }),
    roundtrip: (data) => fromHex(request({ op: 'roundtrip', hex: toHex(data) }).hex),
    resolve: (data, id, strict = false) => request({ op: 'resolve', hex: toHex(data), id, strict }),
    validate: (config, strict = false) => request({ op: 'validate', config, strict }),
    build(config, strict = false) {
      const response = request({ op: 'build', config, strict })
      return { data: fromHex(response.hex), manifest: response.manifest }
    },
    decode: (blob) => fromHex(request({ op: 'decode', hex: toHex(blob) }).hex),
  }
}

/** Host-free codec backed by the same MoonBit WASM as the YKI editor. */
export async function createG7221(wasm) {
  const core = await createCore(wasm)
  return { encode: core.encodeG7221, decode: core.decodeG7221 }
}
