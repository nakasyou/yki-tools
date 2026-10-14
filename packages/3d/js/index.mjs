const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', { fatal: true })
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
/** Create an independent, host-free 3D WASM instance. */
export async function create3D(wasm) {
  const result = await WebAssembly.instantiate(wasm, {})
  const exports = (result.instance ?? result).exports
  function request(value) {
    send(exports, encoder.encode(JSON.stringify(value)), 'input_begin', 'input_write')
    exports.invoke()
    const response = JSON.parse(decoder.decode(receive(exports, 'output_length', 'output_read')))
    if (response.error) throw new Error(response.error)
    return response
  }
  return {
    request,
    generateMedal: (bits, options = {}) => request({ ...options, op: 'generate_medal', bits }),
  }
}
